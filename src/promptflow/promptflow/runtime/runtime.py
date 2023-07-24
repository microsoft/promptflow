# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import multiprocessing
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, List

from promptflow.contracts.error_codes import InvalidRunMode, SubmissionDataDeserializeError
from promptflow.contracts.flow import BatchFlowRequest, EvalRequest, Flow
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import (
    BulkRunRequestV2,
    FlowRequestV2,
    FlowSourceType,
    SingleNodeRequestV2,
    SubmissionRequestBaseV2,
    SubmitFlowRequest,
)
from promptflow.core.connection_manager import ConnectionManager
from promptflow.core.operation_context import OperationContext
from promptflow.core.run_tracker import RunTracker
from promptflow.data import load_data
from promptflow.exceptions import (
    ErrorResponse,
    ExceptionPresenter,
    FlowRunTimeoutError,
    JsonSerializedPromptflowException,
    StorageAuthenticationError,
    UserAuthenticationError,
)
from promptflow.executor.executor import FlowExecutionCoodinator
from promptflow.utils.internal_logger_utils import FileType, SystemLogContext
from promptflow.utils.retry_utils import retry
from promptflow.utils.thread_utils import timeout
from promptflow.utils.timer import Timer

from .._constants import ComputeType, PromptflowEdition
from .connections import (
    build_connection_dict,
    get_used_connection_names_from_environment_variables,
    update_environment_variables_with_connections,
)
from .data import prepare_data
from .error_codes import EmptyDataResolved, UnexpectedFlowSourceType
from .runtime_config import RuntimeConfig, create_tables_for_community_edition, get_executor, load_runtime_config
from .utils import logger, multi_processing_exception_wrapper
from .utils._flow_source_helper import fill_working_dir
from .utils._run_status_helper import mark_runs_as_failed_in_runhistory, mark_runs_as_failed_in_storage_and_runhistory
from .utils._utils import get_storage_from_config

STATUS_CHECKER_INTERVAL = 20  # seconds
MONITOR_REQUEST_TIMEOUT = 10  # seconds
SYNC_SUBMISSION_TIMEOUT = 330  # seconds
WAIT_SUBPROCESS_EXCEPTION_TIMEOUT = 10  # seconds


class PromptFlowRuntime:
    """PromptFlow runtime."""

    _instance = None

    def __init__(self, config: RuntimeConfig):
        self.config = config

    def execute_flow(self, request: SubmissionRequestBaseV2, execute_flow_func: Callable):
        if self.config.execution.execute_in_process:
            result = execute_flow_func(self.config, request)
        else:
            result = execute_flow_request_multiprocessing(self.config, request, execute_flow_func)
        return result

    def execute(self, request: SubmitFlowRequest):
        """execute a flow."""
        # init in main process, so it can be cached
        self.config.init_from_request(request.workspace_msi_token_for_storage_resource)

        if self.config.execution.execute_in_process:
            result = execute_request(self.config, request)
        else:
            result = execute_request_multiprocessing(self.config, request)
        return result

    def mark_flow_runs_as_failed(self, flow_request: SubmitFlowRequest, payload: dict, ex: Exception):
        try:
            code = None
            if isinstance(ex, JsonSerializedPromptflowException):
                error_dict = json.loads(ex.message)
                code = ErrorResponse.from_error_dict(error_dict).innermost_error_code
                logger.info(f"JsonSerializedPromptflowException inner most error code is:{code}.")
            else:
                code = ErrorResponse.from_exception(ex).innermost_error_code
                logger.info(f"Exception innermost_error_code is:{code}.")

            if code == SubmissionDataDeserializeError.__name__ or code == InvalidRunMode.__name__:
                logger.warning(
                    "For SubmissionDataDeserializeError and InvalidRunMode, cannot get the variant run ids, "
                    + "eval run id and bulk test run id, so do nothing."
                )
            elif code == StorageAuthenticationError.__name__:
                logger.info("For StorageAuthenticationError, only mark job as failed in run history.")
                mark_runs_as_failed_in_runhistory(self.config, flow_request, payload, ex)
            elif code == UserAuthenticationError.__name__:
                logger.warning(
                    "For UserAuthenticationError, cannot update run status in both run history "
                    + "and table/blob storage, so do nothing."
                )
            else:
                logger.info("For other error, try to mark job as failed in both run history and table/blob storage.")
                mark_runs_as_failed_in_storage_and_runhistory(self.config, flow_request, payload, ex)
        except Exception as exception:
            logger.warning("Hit exception when mark flow runs as failed: \n%s", ExceptionPresenter(exception).to_dict())

    def init_storage(self):
        """Create tables for local storage (community edition)."""
        if self.config.deployment.edition != PromptflowEdition.COMMUNITY:
            return
        create_tables_for_community_edition(self.config)
        logger.info("Finished creating tables for community edition.")

    def init_operation_context(self):
        OperationContext.get_instance().deploy_config = self.config.deployment

    @classmethod
    def get_instance(cls):
        """get singleton instance."""
        if cls._instance is None:
            cls._instance = PromptFlowRuntime(load_runtime_config())
        return cls._instance

    @classmethod
    def init(cls, config: RuntimeConfig):
        """init runtime with config."""

        cls._instance = PromptFlowRuntime(config)


def execute_request_multiprocessing(config: RuntimeConfig, request: SubmitFlowRequest):
    """execute request in a child process."""
    pid = os.getpid()

    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    user_agent = OperationContext.get_instance().user_agent
    request_id = OperationContext.get_instance().request_id
    exception_queue = multiprocessing.Queue()
    # TODO: change to support streaming output
    p = multiprocessing.Process(
        target=execute_request_multiprocessing_impl,
        args=(config, pid, request, user_agent, return_dict, exception_queue, request_id),
    )
    p.start()
    logger.info("Starting to check process %s status", p.pid)
    start_thread_to_monitor_request_handler_process(
        config=config,
        request=request,
        process=p,
    )

    if request.run_mode in (RunMode.BulkTest, RunMode.Eval):
        p.join()
    else:
        p.join(timeout=SYNC_SUBMISSION_TIMEOUT)

        if p.is_alive():
            logger.error(f"[{p.pid}] Stop flow subprocess for exceeding {SYNC_SUBMISSION_TIMEOUT} seconds.")
            p.terminate()
            p.join()
            raise FlowRunTimeoutError(SYNC_SUBMISSION_TIMEOUT)
    logger.info("Process %s finished", p.pid)
    # when p is killed by signal, exitcode will be negative without exception
    if p.exitcode and p.exitcode > 0:
        exception = None
        try:
            exception = exception_queue.get(timeout=WAIT_SUBPROCESS_EXCEPTION_TIMEOUT)
        except Exception:
            pass
        # JsonSerializedPromptflowException will be raised here
        # no need to change to PromptflowException since it will be handled in app.handle_exception
        # we can unify the exception when we decide to expose executor.execute as an public API
        if exception is not None:
            raise exception
    result = return_dict.get("result", {})

    logger.info("[%s] Child process finished!", pid)
    return result


def start_thread_to_monitor_request_handler_process(config: RuntimeConfig, request: SubmitFlowRequest, process):
    """Start a thread to monitor request handler process.
    When request cancel is received, it will
    1. terminate the request handler process.
    2. mark the run as canceled.
    """
    token = request.workspace_msi_token_for_storage_resource
    bulk_test_run_ids = FlowExecutionCoodinator.get_bulk_test_variants_run_ids(req=request)

    def get_run_ids_status(run_ids):
        storage = get_storage_from_config(config, token=token)
        status = {}
        for run_id in run_ids:
            run_status = storage.get_run_status(run_id=run_id)
            status[run_id] = run_status
        return status

    def kill_process():
        if process.is_alive():
            # TODO(2423785): terminate the process gracefully
            process.kill()
            logger.info("Successfully terminated process with pid %s", process.pid)
        else:
            logger.info("Process already terminated")
        return True

    def kill_evaluation_process() -> bool:
        if process.is_alive():
            # check if all evaluation runs are terminated
            status = get_run_ids_status(bulk_test_run_ids)
            if all([Status.is_terminated(s) for s in status.values()]):
                # TODO(2423785): terminate the process gracefully
                process.kill()
                logger.info("Successfully terminated process with pid %s", process.pid)
                return True
            else:
                logger.info("Not all variants reached terminated status: %s", status)
                return False
        else:
            logger.info("Process already canceled for evaluation process %s", process.pid)
            return True

    # add timeout & retry to avoid request stuck issue
    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def get_storage_from_config_with_retry():
        return get_storage_from_config(
            config,
            token=token,
            azure_storage_setting=request.azure_storage_setting,
            run_mode=request.run_mode,
        )

    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def get_run_status_with_retry(storage, run_id):
        return storage.get_run_status(run_id=run_id)

    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def cancel_run_with_retry(storage, run_id):
        return storage.cancel_run(run_id=run_id)

    def monitor_run_status(
        run_id: str,
        run_ids: List[str],
        kill_process,
        request: SubmitFlowRequest,
        log_target_run_id: str,
        request_id: str,
    ):
        try:
            operation_context = OperationContext.get_instance()
            operation_context.request_id = request_id
            operation_context.run_mode = request.run_mode.name if request.run_mode is not None else ""
            # Set log context here;
            # otherwise the previously set context-local log handlers/filters will be lost.
            custom_dimensions = operation_context.get_context_dict()
            log_context = get_log_context(request, config.deployment.edition, log_target_run_id, custom_dimensions)
            with log_context:
                storage = get_storage_from_config_with_retry()
                logger.info("Start checking run status for run %s", run_id)
                while True:
                    # keep monitoring to make sure long running process can be terminated
                    time.sleep(STATUS_CHECKER_INTERVAL)

                    run_status = get_run_status_with_retry(storage=storage, run_id=run_id)
                    if run_status is None:
                        logger.info("Run %s not found, end execution monitoring", run_id)
                        return
                    logger.info("Run %s is in progress, Execution status: %s", run_id, run_status)
                    if run_status == Status.CancelRequested.value:
                        logger.info("Cancel requested for run %s", run_id)
                        try:
                            # terminate the process gracefully
                            killed = kill_process()
                            if not killed:
                                continue
                            # mark the run as canceled
                            for child_run_id in run_ids:
                                logger.info("Updating status for run %s", child_run_id)
                                cancel_run_with_retry(storage=storage, run_id=child_run_id)
                            logger.info("Successfully canceled run %s with child runs %s", run_id, run_ids)
                            return
                        except Exception as e:
                            logger.error("Failed to kill process for run %s due to %s", run_id, e, exc_info=True)
                            return
                    elif Status.is_terminated(run_status):
                        logger.debug("Run %s is in terminate status %s", run_id, run_status)
                        return
        except Exception as e:
            logger.warning("Failed to monitor run status for run %s due to %s", run_id, e, exc_info=True)

    # monitor bulk test & evaluation
    if request.run_mode in [RunMode.BulkTest, RunMode.Eval]:
        # need to monitor variant run's parent run status, which stores in bulk_test_id
        run_id = request.submission_data.bulk_test_id
        logger.info("Start checking run status for bulk run %s", run_id)
        # cancel the parent run(run_id) as well as all its child runs
        all_run_ids = FlowExecutionCoodinator.get_root_run_ids(req=request) + [run_id]
        thread = threading.Thread(
            name="monitor_bulk_run_status",
            target=monitor_run_status,
            kwargs={
                "run_id": run_id,
                "run_ids": all_run_ids,
                "kill_process": kill_process,
                "request": request,
                "log_target_run_id": request.flow_run_id,
                "request_id": OperationContext.get_instance().request_id,
            },
            daemon=True,
        )
        thread.start()

    # monitor evaluation if bulk test has one
    if request.run_mode == RunMode.BulkTest and request.submission_data and request.submission_data.eval_flow:
        run_id = request.submission_data.eval_flow_run_id
        logger.info("Start checking run status for evaluation run %s", run_id)
        thread = threading.Thread(
            name="monitor_evaluation_status",
            target=monitor_run_status,
            kwargs={
                "run_id": run_id,
                "run_ids": [run_id],
                "kill_process": kill_evaluation_process,
                "request": request,
                "log_target_run_id": run_id,
                "request_id": OperationContext.get_instance().request_id,
            },
            daemon=True,
        )
        thread.start()


def execute_request_multiprocessing_impl(
    config: RuntimeConfig,
    parent_pid: int,
    request: SubmitFlowRequest,
    user_agent: str,
    return_dict,
    exception_queue,
    request_id: str = None,
):
    """execute request in a child process.
    the child process should execute inside multi_processing_exception_wrapper to avoide exception issue.
    """
    operation_context = OperationContext.get_instance()
    operation_context.deploy_config = config.deployment
    operation_context.user_agent = user_agent
    operation_context.request_id = request_id
    operation_context.run_mode = request.run_mode.name if request.run_mode is not None else ""
    with multi_processing_exception_wrapper(exception_queue):
        # set log context here;
        # otherwise the previously set context-local log handlers/filters will be lost
        # because this method is invoked in another process.
        with get_log_context(
            request, config.deployment.edition, custom_dimensions=operation_context.get_context_dict()
        ):
            logger.info("[%s--%s] Start processing flow......", parent_pid, os.getpid())
            result = execute_request(config, request)
            return_dict["result"] = result


def set_environment_variables(env_vars: dict):
    """set environment variables."""
    if env_vars:
        for key, value in env_vars.items():
            os.environ[key] = value


def resolve_data_from_uri(data_uri, destination: str, runtime_config: RuntimeConfig, inputs: set):
    data = None
    if data_uri:
        from .utils._token_utils import get_default_credential

        with Timer(logger, "Resolve data from url"):
            credential = get_default_credential()
            # resolve data uri to local data
            local_file = prepare_data(
                data_uri, destination=destination, credential=credential, runtime_config=runtime_config
            )

            data = load_data(local_file, logger=logger)
            if not data:
                raise EmptyDataResolved(message_format="resolve empty data from data_uri")

            # filter cols that exists in inputs
            result = []
            for line in data:
                r = {}
                for k, v in line.items():
                    if k in inputs:
                        r[k] = v
                result.append(r)
            data = result
            logger.info(
                "Resolved %s lines of data from uri: {customer_content}",
                len(data),
                extra={"customer_content": data_uri},
            )
    return data


DATA_PREFIX = "data."


def parse_data_mapping(s):
    if not s.startswith(DATA_PREFIX):
        return None
    return s[len(DATA_PREFIX) :]


def get_required_inputs(submit_request: SubmitFlowRequest) -> set:
    """get required inputs from flow"""
    req = submit_request.submission_data
    flow_inputs = set(req.flow.inputs.keys())
    if isinstance(req, EvalRequest):
        #  If mapping is not provided, simply use the flow inputs
        if req.inputs_mapping is None:
            return flow_inputs
        return {parse_data_mapping(v) for v in req.inputs_mapping.values() if v.startswith(DATA_PREFIX)}

    if isinstance(req, BatchFlowRequest) and req.eval_flow_inputs_mapping:
        eval_data_inputs = {
            parse_data_mapping(v) for v in req.eval_flow_inputs_mapping.values() if v.startswith(DATA_PREFIX)
        }
        return flow_inputs | eval_data_inputs

    return flow_inputs


def resolve_data(submit_flow_request: SubmitFlowRequest, destination: str, runtime_config: RuntimeConfig):
    """resolve data uri"""
    run_mode = submit_flow_request.run_mode

    inputs = get_required_inputs(submit_flow_request)

    if run_mode in (RunMode.Flow, run_mode.BulkTest) and submit_flow_request.batch_data_input:
        data_uri = submit_flow_request.batch_data_input.data_uri
        if data_uri:
            data = resolve_data_from_uri(data_uri, destination, runtime_config, inputs)
            req: BatchFlowRequest = submit_flow_request.submission_data
            req.batch_inputs = data

    if run_mode == RunMode.Eval and submit_flow_request.bulk_test_data_input:
        data_uri = submit_flow_request.bulk_test_data_input.data_uri
        if data_uri:
            data = resolve_data_from_uri(data_uri, destination, runtime_config, inputs)
            req_eval: EvalRequest = submit_flow_request.submission_data
            req_eval.bulk_test_inputs = data


def execute_flow_request_multiprocessing_impl(
    execute_flow_func: Callable,
    config: RuntimeConfig,
    parent_pid: int,
    request: SubmissionRequestBaseV2,
    user_agent: str,
    return_dict,
    exception_queue,
    request_id: str = None,
):
    """execute flow request V2 in a child process.
    the child process should execute inside multi_processing_exception_wrapper to avoide exception issue.
    """
    operation_context = OperationContext.get_instance()
    operation_context.deploy_config = config.deployment
    operation_context.user_agent = user_agent
    operation_context.request_id = request_id
    operation_context.run_mode = request.get_run_mode()
    with multi_processing_exception_wrapper(exception_queue):
        # set log context here;
        # otherwise the previously set context-local log handlers/filters will be lost
        # because this method is invoked in another process.
        log_context = get_log_context_from_v2_request(
            request, config.deployment.edition, custom_dimensions=operation_context.get_context_dict())
        with log_context:
            logger.info("[%s--%s] Start processing flowV2......", parent_pid, os.getpid())
            result = execute_flow_func(config, request)
            return_dict["result"] = result


def execute_flow_request_multiprocessing(config: RuntimeConfig, request: SubmissionRequestBaseV2, execute_flow_func):
    """execute request in a child process."""
    pid = os.getpid()

    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    user_agent = OperationContext.get_instance().user_agent
    request_id = OperationContext.get_instance().request_id
    exception_queue = multiprocessing.Queue()
    # TODO: change to support streaming output
    p = multiprocessing.Process(
        target=execute_flow_request_multiprocessing_impl,
        args=(execute_flow_func, config, pid, request, user_agent, return_dict, exception_queue, request_id),
    )
    p.start()

    if isinstance(request, BulkRunRequestV2):
        logger.info("Starting to check process %s status for run %s", p.pid, request.flow_run_id)
        start_thread_to_monitor_request_V2_handler_process(
            config=config,
            request=request,
            process=p,
        )
        p.join()
    else:
        # MT timeout 300s for sync submission.
        # Timeout longer than MT to avoid exception thrown early
        p.join(timeout=SYNC_SUBMISSION_TIMEOUT)

        if p.is_alive():
            logger.error(f"[{p.pid}] Stop flow subprocess for exceeding {SYNC_SUBMISSION_TIMEOUT} seconds.")
            p.terminate()
            p.join()
            raise FlowRunTimeoutError(SYNC_SUBMISSION_TIMEOUT)
    logger.info("Process %s finished", p.pid)
    # when p is killed by signal, exitcode will be negative without exception
    if p.exitcode and p.exitcode > 0:
        exception = None
        try:
            exception = exception_queue.get(timeout=WAIT_SUBPROCESS_EXCEPTION_TIMEOUT)
        except Exception:
            pass
        # JsonSerializedPromptflowException will be raised here
        # no need to change to PromptflowException since it will be handled in app.handle_exception
        # we can unify the exception when we decide to expose executor.execute as an public API
        if exception is not None:
            raise exception
    result = return_dict.get("result", {})

    logger.info("[%s] Child process finished!", pid)
    return result


def execute_node_request(config: RuntimeConfig, request: SingleNodeRequestV2):
    origin_wd = os.getcwd()
    working_dir = None
    try:
        set_environment_variables(request.environment_variables)
        connection_names = get_used_connection_names_from_environment_variables()
        built_connections = build_connection_dict(
            connection_names=connection_names,
            subscription_id=config.deployment.subscription_id,
            resource_group=config.deployment.resource_group,
            workspace_name=config.deployment.workspace_name,
        )
        update_environment_variables_with_connections(built_connections)
        working_dir = Path(f"requests/{request.flow_run_id}")
        working_dir.mkdir(parents=True, exist_ok=True)
        if request.flow_source.flow_source_type != FlowSourceType.AzureFileShare:
            raise UnexpectedFlowSourceType(message_format="Node request should be from Azure File Share")
        working_dir = fill_working_dir(
            config.deployment.compute_type, request.flow_source.flow_source_info, request.flow_run_id
        )
        # Node run doesn't need to set storage.
        coodinator = FlowExecutionCoodinator.init_with_run_tracker(RunTracker.init_dummy())
        run_tracker = coodinator._run_tracker
        run_tracker._activate_in_context()
        dag_file = request.flow_source.flow_dag_file
        try:
            # TODO: Refactor to use FlowExecutor, NodesExecutor will not open source.
            nodes_executor = coodinator.create_nodes_executor_by_yaml(
                dag_file, request.node_name, request.inputs, request.connections, Path(working_dir)
            )
            nodes_executor.exec_nodes(
                request.inputs,
                request.get_run_mode(),
                request.node_name,
            )
        finally:
            run_tracker._deactivate_in_context()
        return run_tracker.collect_all_run_infos_as_dicts()
    finally:
        os.chdir(origin_wd)
        # post process: clean up and restore working dir
        # note: no need to clean environment variables, because they are only set in child process
        if working_dir and not config.execution.debug:
            # remove working dir if not debug mode
            if (
                config.deployment.compute_type == ComputeType.COMPUTE_INSTANCE
                and request.flow_source is not None
                and request.flow_source.flow_source_type == FlowSourceType.AzureFileShare
            ):
                # Don't remove working dir when it is CI mounting dir
                pass
            else:
                logger.info("Cleanup working dir %s", working_dir)
                shutil.rmtree(working_dir, ignore_errors=True)


def execute_flow_request(config: RuntimeConfig, request: FlowRequestV2):
    origin_wd = os.getcwd()
    working_dir = None
    try:
        set_environment_variables(request.environment_variables)
        connection_names = get_used_connection_names_from_environment_variables()
        built_connections = build_connection_dict(
            connection_names=connection_names,
            subscription_id=config.deployment.subscription_id,
            resource_group=config.deployment.resource_group,
            workspace_name=config.deployment.workspace_name,
        )
        update_environment_variables_with_connections(built_connections)
        working_dir = Path(f"requests/{request.flow_run_id}")
        working_dir.mkdir(parents=True, exist_ok=True)
        if request.flow_source.flow_source_type != FlowSourceType.AzureFileShare:
            raise UnexpectedFlowSourceType(message_format="Flow request should be from Azure File Share")
        working_dir = fill_working_dir(
            config.deployment.compute_type, request.flow_source.flow_source_info, request.flow_run_id
        )
        # Flow run doesn't need to set storage.
        coodinator = FlowExecutionCoodinator.init_with_run_tracker(RunTracker.init_dummy())
        run_tracker = coodinator._run_tracker
        run_tracker._activate_in_context()
        flow_id, run_id = request.flow_id, request.flow_run_id
        dag_file = request.flow_source.flow_dag_file
        root_run_info = run_tracker.start_flow_run(flow_id, run_id, run_id)
        try:
            flow_executor = coodinator.create_flow_executor_by_yaml(dag_file, request.connections, Path(working_dir))
            flow_executor._run_tracker._activate_in_context()
            line_result = flow_executor.exec_line(request.inputs, index=0, parent=root_run_info)
            if flow_executor.has_aggregation_node:
                inputs_list = {k: [v] for k, v in request.inputs.items()}
                aggregation_inputs_list = {k: [v] for k, v in line_result.aggregation_inputs.items()}
                flow_executor.exec_aggregation(inputs_list, aggregation_inputs_list, root_run_info)
            flow_executor._run_tracker._deactivate_in_context()
            run_tracker.end_run(run_id, result=[])
        except Exception as e:
            run_tracker.end_run(run_id, ex=e)
        finally:
            run_tracker._deactivate_in_context()
        return run_tracker.collect_all_run_infos_as_dicts()
    finally:
        os.chdir(origin_wd)
        # post process: clean up and restore working dir
        # note: no need to clean environment variables, because they are only set in child process
        if working_dir and not config.execution.debug:
            # remove working dir if not debug mode
            if (
                config.deployment.compute_type == ComputeType.COMPUTE_INSTANCE
                and request.flow_source is not None
                and request.flow_source.flow_source_type == FlowSourceType.AzureFileShare
            ):
                # Don't remove working dir when it is CI mounting dir
                pass
            else:
                logger.info("Cleanup working dir %s", working_dir)
                shutil.rmtree(working_dir, ignore_errors=True)


def execute_bulk_run_request(config: RuntimeConfig, request: BulkRunRequestV2):
    origin_wd = os.getcwd()
    working_dir = None
    try:
        # Keep a large try-catch scope, guarantee all exception be recorded in RH.
        try:
            set_environment_variables(request.environment_variables)
            connection_names = get_used_connection_names_from_environment_variables()
            built_connections = build_connection_dict(
                connection_names=connection_names,
                subscription_id=config.deployment.subscription_id,
                resource_group=config.deployment.resource_group,
                workspace_name=config.deployment.workspace_name,
            )
            update_environment_variables_with_connections(built_connections)
            run_storage = config.get_run_storage(
                workspace_access_token=None,
                azure_storage_setting=request.azure_storage_setting,
                run_mode=request.get_run_mode(),
            )
            # TODO:
            # For open source, we should create FlowExecutor directly (without FlowExecutionCoodinator).
            # And will move RH operation out of RunTracker.
            coodinator = FlowExecutionCoodinator.init_with_run_tracker(
                RunTracker(run_storage=run_storage, run_mode=request.get_run_mode())
            )
            run_tracker = coodinator._run_tracker
            run_tracker._activate_in_context()
            flow_id, run_id = request.flow_id, request.flow_run_id
            dag_file = request.flow_source.flow_dag_file
            root_run_info = run_tracker.start_root_flow_run(
                flow_id=flow_id, root_run_id=run_id, run_id=run_id, parent_run_id=""
            )

            # Start to download folder.
            working_dir = Path(f"requests/{request.flow_run_id}")
            working_dir.mkdir(parents=True, exist_ok=True)
            if request.flow_source.flow_source_type != FlowSourceType.Snapshot:
                raise UnexpectedFlowSourceType(message_format="Bulk run request data should be from Snapshot.")
            snapshot_client = config.get_snapshot_client()
            snapshot_client.download_snapshot(request.flow_source.flow_source_info.snapshot_id, working_dir)

            # Start to download inputs.
            input_dicts = {}
            for input_key, input_url in request.data_inputs.items():
                with Timer(logger, "Resolve data from url"):
                    # resolve data uri to local data
                    local_file = prepare_data(
                        input_url, destination=working_dir / "inputs" / input_key, runtime_config=config
                    )
                    data = load_data(local_file, logger=logger)
                    input_dicts[input_key] = data

            flow_executor = coodinator.create_flow_executor_by_yaml(dag_file, request.connections, Path(working_dir))
            mapped_inputs = flow_executor.apply_inputs_mapping_for_all_lines(input_dicts, request.inputs_mapping)
            bulk_result = flow_executor.exec_batch(mapped_inputs, root_run_info)
            status_summary = run_tracker.get_status_summary(run_id)
            run_tracker.persist_status_summary(status_summary, run_id)
            run_tracker.end_run(run_id, result=bulk_result, update_at_last=True)
        except Exception as e:
            run_tracker.end_run(run_id, ex=e, update_at_last=True)
        finally:
            run_tracker._deactivate_in_context()
            # Todo: end bulk test
        return run_tracker.collect_all_run_infos_as_dicts()
    finally:
        os.chdir(origin_wd)
        # post process: clean up and restore working dir
        # note: no need to clean environment variables, because they are only set in child process
        if working_dir and not config.execution.debug:
            # remove working dir if not debug mode
            shutil.rmtree(working_dir, ignore_errors=True)


def execute_request(config: RuntimeConfig, request: SubmitFlowRequest):
    """execute request in child process."""
    origin_wd = os.getcwd()
    executor = None
    working_dir = None
    try:
        # pre process: set environment variables & prepare input data
        set_environment_variables(request.environment_variables)
        token = request.workspace_msi_token_for_storage_resource
        executor = get_executor(
            config,
            workspace_access_token=token,
            azure_storage_setting=request.azure_storage_setting,
            run_mode=request.run_mode,
        )
        # enrich run tracker with the run mode, to determine if we need to update run history
        executor._run_tracker._run_mode = request.run_mode

        assert request.flow_run_id

        working_dir = Path(f"requests/{request.flow_run_id}")
        working_dir.mkdir(parents=True, exist_ok=True)
        if request.flow_source is not None:
            flow_source = request.flow_source
            if flow_source.flow_source_type == FlowSourceType.Snapshot:
                snapshot_client = config.get_snapshot_client()
                snapshot_client.download_snapshot(flow_source.flow_source_info.snapshot_id, working_dir)
            elif flow_source.flow_source_type == FlowSourceType.AzureFileShare:
                working_dir = fill_working_dir(
                    config.deployment.compute_type, request.flow_source.flow_source_info, request.flow_run_id
                )
            else:
                raise NotImplementedError(
                    f"Flow source type {flow_source.flow_source_type} is not supported in current version."
                )

            yaml_file = flow_source.flow_dag_file
            # Note that the resolving logic should be in child process since it would add working_dir to sys.path,
            # which we do not want to add to the parent process and make it very long
            flow = Flow.from_yaml(flow_file=yaml_file, working_dir=working_dir)
            flow.id = request.flow_id
            request.submission_data.flow = flow
        os.chdir(working_dir)

        # resolve data in user folder
        resolve_data(request, destination="./inputs", runtime_config=config)

        # execute
        # When it is CI compute and AzureFileShare flow source, working dir may be customer content
        logger.info(
            "Start execute request: %s in dir {customer_content}...",
            request.flow_run_id,
            extra={"customer_content": working_dir},
        )
        result = executor.exec_request_raw(request)
    finally:
        os.chdir(origin_wd)
        # post process: clean up and restore working dir
        # note: no need to clean environment variables, because they are only set in child process
        if working_dir and not config.execution.debug:
            # remove working dir if not debug mode
            if (
                config.deployment.compute_type == ComputeType.COMPUTE_INSTANCE
                and request.flow_source is not None
                and request.flow_source.flow_source_type == FlowSourceType.AzureFileShare
            ):
                # Don't remove working dir when it is CI mounting dir
                pass
            else:
                logger.info("Cleanup working dir %s", working_dir)
                shutil.rmtree(working_dir, ignore_errors=True)

    return result


def get_credential_list_for_v2_request(req: SubmissionRequestBaseV2) -> List[str]:
    credential_list = ConnectionManager(req.connections).get_secret_list()
    if req.app_insights_instrumentation_key:
        credential_list.append(req.app_insights_instrumentation_key)
    return credential_list


def get_credential_list_from_request(request: SubmitFlowRequest) -> List[str]:
    """Get credential list from submission data.

    Credentials include:
        1. api keys in connections;
        2. app insights instrumentation key.
    """
    connections = request.submission_data.connections
    credential_list = ConnectionManager(connections).get_secret_list()
    if request.app_insights_instrumentation_key:
        credential_list.append(request.app_insights_instrumentation_key)
    return credential_list


def get_log_context(
        request: SubmitFlowRequest,
        edition: PromptflowEdition,
        run_id: Optional[str] = None,
        custom_dimensions: Optional[Dict[str, str]] = None) -> SystemLogContext:

    if run_id is None:
        run_id = request.flow_run_id
    file_path = request.run_id_to_log_path.get(run_id) if request.run_id_to_log_path else None
    file_type = FileType.Blob if edition == PromptflowEdition.ENTERPRISE else FileType.Local

    if custom_dimensions:
        custom_dimensions.update({"root_flow_run_id": request.flow_run_id})

    return SystemLogContext(
        file_path=file_path,
        run_mode=request.run_mode,
        credential_list=get_credential_list_from_request(request),
        file_type=file_type,
        custom_dimensions=custom_dimensions,
        app_insights_instrumentation_key=request.app_insights_instrumentation_key,
        input_logger=logger,
    )


def get_log_context_from_v2_request(
        request: SubmissionRequestBaseV2,
        edition: PromptflowEdition,
        custom_dimensions: Optional[Dict[str, str]] = None) -> SystemLogContext:

    run_mode = RunMode.Flow
    if isinstance(request, FlowRequestV2):
        run_mode = RunMode.Flow
    elif isinstance(request, BulkRunRequestV2):
        run_mode = RunMode.BulkTest
    elif isinstance(request, SingleNodeRequestV2):
        run_mode = RunMode.SingleNode
    else:
        # Do we need to raise another exception here? It should never happen.
        raise NotImplementedError(f"Unsupported request type: {type(request)}")

    file_type = FileType.Blob if edition == PromptflowEdition.ENTERPRISE else FileType.Local

    if custom_dimensions:
        custom_dimensions.update({"root_flow_run_id": request.flow_run_id})

    return SystemLogContext(
        file_path=request.log_path,
        run_mode=run_mode,
        credential_list=get_credential_list_for_v2_request(request),
        file_type=file_type,
        custom_dimensions=custom_dimensions,
        app_insights_instrumentation_key=request.app_insights_instrumentation_key,
        input_logger=logger,
    )


def start_thread_to_monitor_request_V2_handler_process(
    config: RuntimeConfig, request: SubmissionRequestBaseV2, process
):
    """Start a thread to monitor V2 request handler process.
    When request cancel is received, it will
    1. terminate the request handler process.
    2. mark the run as canceled.
    """

    def kill_process():
        if process.is_alive():
            # TODO(2423785): terminate the process gracefully
            process.kill()
            logger.info("Successfully terminated process with pid %s", process.pid)
        else:
            logger.info("Process already terminated")
        return True

    # add timeout & retry to avoid request stuck issue
    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def get_storage_from_config_with_retry():
        return get_storage_from_config(config, run_mode=RunMode.BulkTest)

    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def get_run_status_with_retry(storage, run_id):
        return storage.get_run_status(run_id=run_id)

    @retry(TimeoutError, tries=3, logger=logger)
    @timeout(timeout_seconds=MONITOR_REQUEST_TIMEOUT)
    def cancel_run_with_retry(storage, run_id):
        return storage.cancel_run(run_id=run_id)

    def monitor_run_status(run_id: str, kill_process, request: SubmissionRequestBaseV2, request_id: str):
        try:
            operation_context = OperationContext.get_instance()
            operation_context.request_id = request_id
            operation_context.run_mode = request.get_run_mode()
            # Set log context here;
            # otherwise the previously set context-local log handlers/filters will be lost,
            log_context = get_log_context_from_v2_request(
                request,
                config.deployment.edition,
                custom_dimensions=operation_context.get_context_dict())
            with log_context:
                storage = get_storage_from_config_with_retry()
                logger.info("Start checking run status for run %s", run_id)
                while True:
                    # keep monitoring to make sure long running process can be terminated
                    time.sleep(STATUS_CHECKER_INTERVAL)

                    run_status = get_run_status_with_retry(storage=storage, run_id=run_id)
                    if run_status is None:
                        logger.info("Run %s not found, end execution monitoring", run_id)
                        return
                    logger.info("Run %s is in progress, Execution status: %s", run_id, run_status)
                    if run_status == Status.CancelRequested.value:
                        logger.info("Cancel requested for run %s", run_id)
                        try:
                            # terminate the process gracefully
                            killed = kill_process()
                            if not killed:
                                continue
                            logger.info("Updating status for run %s", run_id)
                            cancel_run_with_retry(storage=storage, run_id=run_id)
                            logger.info("Successfully canceled run %s", run_id)
                            # mark the run as canceled
                            return
                        except Exception as e:
                            logger.error("Failed to kill process for run %s due to %s", run_id, e, exc_info=True)
                            return
                    elif Status.is_terminated(run_status):
                        logger.debug("Run %s is in terminate status %s", run_id, run_status)
                        return
        except Exception as e:
            logger.warning("Failed to monitor run status for run %s due to %s", run_id, e, exc_info=True)

    run_id = request.flow_run_id
    logger.info("Start checking run status for bulk run %s", run_id)
    # cancel the parent run(run_id) as well as all its child runs
    thread = threading.Thread(
        name="monitor_bulk_run_status",
        target=monitor_run_status,
        kwargs={
            "run_id": run_id,
            "kill_process": kill_process,
            "request": request,
            "request_id": OperationContext.get_instance().request_id,
        },
        daemon=True,
    )
    thread.start()
