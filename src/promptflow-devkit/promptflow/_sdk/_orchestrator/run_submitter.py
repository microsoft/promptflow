# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor, it'll have some similar logic with cloud PFS.

import datetime
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Union

from promptflow._constants import SystemMetricKeys
from promptflow._sdk._constants import ContextAttributeKey, FlowRunProperties
from promptflow._sdk.entities._flows import Flow, Prompty
from promptflow._sdk.entities._run import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.flow_utils import parse_variant
from promptflow._utils.logger_utils import LoggerFactory
from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import UserErrorException, ValidationException
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._start_trace import is_collection_writeable, start_trace

from .._load_functions import load_flow
from ..entities._flows import FlexFlow
from .utils import SubmitterHelper, flow_overwrite_context

logger = LoggerFactory.get_logger(name=__name__)


class RunSubmitter:
    """Submit run to executor."""

    def __init__(self, client):
        self._client = client
        self._config = self._client._config
        self.run_operations = self._client.runs

    def submit(self, run: Run, stream=False, **kwargs):
        upload_to_cloud = self._config._is_cloud_trace_destination(path=run._get_flow_dir().resolve())
        if upload_to_cloud:
            logger.info(f"Upload run to cloud: {upload_to_cloud}")
        with ThreadPoolExecutor() as executor:
            # if upload to cloud, initialize async run uploader simultaneously with run execution to improve performance
            tasks = [
                executor.submit(self._run_bulk, run=run, stream=stream, **kwargs),
                executor.submit(self._initialize_async_run_uploader, run=run, upload_to_cloud=upload_to_cloud),
            ]
            wait(tasks, return_when=ALL_COMPLETED)
            task_results = [task.result() for task in tasks]

        # upload run to cloud if the trace destination is set to cloud
        if upload_to_cloud:
            logger.info(f"Uploading run {run.name!r} to cloud...")
            uploader, pfazure_client = task_results[1]
            portal_url = pfazure_client.runs._upload(run=run, run_uploader=uploader)
            logger.info(f"Updating run {run.name!r} portal url to {portal_url!r}.")
            if portal_url is not None:
                self.run_operations.update(name=run.name, portal_url=portal_url)

        return self.run_operations.get(name=run.name)

    def resume(self, resume_from: str, **kwargs):
        resume_from_run = self._ensure_run_completed(resume_from)
        run = resume_from_run._copy(resume_from=resume_from_run.name, **kwargs)
        self._run_bulk(run=run, **kwargs)
        return self.run_operations.get(name=run.name)

    def _ensure_run_completed(self, required_run: Union[str, Run]):
        """Ensure the required run is completed and return the run object."""
        if isinstance(required_run, str):
            required_run = self.run_operations.get(name=required_run)
        elif not isinstance(required_run, Run):
            error = TypeError(f"Referenced run must be a Run instance, got {type(required_run)}")
            raise UserErrorException(message=str(error), error=error)
        else:
            # get the run again to make sure it's status is latest
            required_run = self.run_operations.get(name=required_run.name)
        if required_run.status != Status.Completed.value:
            error = ValueError(f"Referenced run {required_run.name} is not completed, got status {required_run.status}")
            raise UserErrorException(message=str(error), error=error)
        required_run.outputs = self.run_operations._get_outputs(required_run)
        return required_run

    def _run_bulk(self, run: Run, stream=False, **kwargs):
        attributes: dict = kwargs.get("attributes", {})
        # validate & resolve variant
        if run.variant:
            tuning_node, variant = parse_variant(run.variant)
        else:
            tuning_node, variant = None, None

        # always remove reference.batch_run_id from operation context to avoid mis-inheritance
        operation_context = OperationContext.get_instance()
        operation_context._remove_otel_attributes(ContextAttributeKey.REFERENCED_BATCH_RUN_ID)
        if run.run is not None:
            # Set for flow test against run and no experiment scenario
            if ContextAttributeKey.REFERENCED_BATCH_RUN_ID not in attributes:
                referenced_batch_run_id = run.run.name if isinstance(run.run, Run) else run.run
                attributes[ContextAttributeKey.REFERENCED_BATCH_RUN_ID] = referenced_batch_run_id
            run.run = self._ensure_run_completed(run.run)
        if run._resume_from is not None:
            logger.debug(f"Resume from run {run._resume_from!r}...")
            run._resume_from = self._ensure_run_completed(run._resume_from)
        # start trace
        logger.debug("start trace for flow run...")
        flow_path = run._get_flow_dir().resolve()
        logger.debug("flow path for run.start_trace: %s", flow_path)
        if is_collection_writeable():
            logger.debug("trace collection is writeable, will use flow name as collection...")
            collection_for_run = run._flow_name
            logger.debug("collection for run: %s", collection_for_run)
            # pass with internal parameter `_collection`
            start_trace(
                attributes=attributes,
                run=run,
                _collection=collection_for_run,
                path=flow_path,
            )
        else:
            logger.debug("trace collection is protected, will honor existing collection.")
            start_trace(attributes=attributes, run=run, path=flow_path)

        self._validate_inputs(run=run)

        local_storage = LocalStorageOperations(run, stream=stream, run_mode=RunMode.Batch)
        with local_storage.logger:
            flow_obj = load_flow(source=run.flow)
            with flow_overwrite_context(
                flow_obj, tuning_node, variant, connections=run.connections, init_kwargs=run.init
            ) as flow:
                self._submit_bulk_run(flow=flow, run=run, local_storage=local_storage, **kwargs)

    @classmethod
    def _validate_inputs(cls, run: Run):
        if not run.run and not run.data and not run._resume_from:
            error = ValidationException("Either run or data or resume from run must be specified for flow run.")
            raise UserErrorException(message=str(error), error=error)

    def _submit_bulk_run(
        self, flow: Union[Flow, FlexFlow, Prompty], run: Run, local_storage: LocalStorageOperations, **kwargs
    ) -> dict:
        logger.info(f"Submitting run {run.name}, log path: {local_storage.logger.file_path}")
        run_id = run.name

        with _change_working_dir(flow.code):
            # resolve connections with environment variables overrides to avoid getting unused connections
            logger.debug(
                f"Resolving connections for flow {flow.path} with environment variables {run.environment_variables}."
            )
            connections = SubmitterHelper.resolve_connections(
                flow=flow, environment_variables_overrides=run.environment_variables
            )
        column_mapping = run.column_mapping
        # resolve environment variables
        run.environment_variables = SubmitterHelper.load_and_resolve_environment_variables(
            flow=flow, environment_variable_overrides=run.environment_variables
        )
        SubmitterHelper.init_env(environment_variables=run.environment_variables)

        # prepare data
        input_dirs = self._resolve_input_dirs(run)
        self._validate_column_mapping(column_mapping)
        batch_result = None
        status = Status.Failed.value
        exception = None
        # create run to db when fully prepared to run in executor, otherwise won't create it
        run._status = Status.Running.value
        run._start_time = datetime.datetime.now().astimezone()
        run._dump()  # pylint: disable=protected-access

        resume_from_run_storage = (
            LocalStorageOperations(run._resume_from, run_mode=RunMode.Batch) if run._resume_from else None
        )
        try:
            batch_engine = BatchEngine(
                run._dynamic_callable or flow.path,
                flow.code,
                connections=connections,
                entry=flow.entry if isinstance(flow, FlexFlow) else None,
                storage=local_storage,
                log_path=local_storage.logger.file_path,
                init_kwargs=run.init,
                **kwargs,
            )
            batch_result = batch_engine.run(
                input_dirs=input_dirs,
                inputs_mapping=column_mapping,
                output_dir=local_storage.outputs_folder,
                run_id=run_id,
                resume_from_run_storage=resume_from_run_storage,
                resume_from_run_output_dir=resume_from_run_storage.outputs_folder if resume_from_run_storage else None,
            )
            error_logs = []
            if batch_result.failed_lines > 0:
                # Log warning message when there are failed line run in bulk run.
                error_logs.append(
                    f"{batch_result.failed_lines} out of {batch_result.total_lines} runs failed in batch run."
                )
            if batch_result.error_summary.aggr_error_dict:
                # log warning message when there are failed aggregation nodes in bulk run.
                aggregation_nodes = list(batch_result.error_summary.aggr_error_dict.keys())
                error_logs.append(f"aggregation nodes {aggregation_nodes} failed in batch run.")
            # update error log
            if error_logs and run.properties.get(FlowRunProperties.OUTPUT_PATH, None):
                error_logs.append(
                    f" Please check out {run.properties[FlowRunProperties.OUTPUT_PATH]} for more details."
                )
            if error_logs:
                logger.warning("\n".join(error_logs))
            # The bulk run is completed if the batch_engine.run successfully completed.
            status = Status.Completed.value
        except Exception as e:
            # when run failed in executor, store the exception in result and dump to file
            logger.warning(f"Run {run.name} failed when executing in executor with exception {e}.")
            exception = e
            # for user error, swallow stack trace and return failed run since user don't need the stack trace
            if not isinstance(e, UserErrorException):
                # for other errors, raise it to user to help debug root cause.
                raise e
            # won't raise the exception since it's already included in run object.
        finally:
            # persist snapshot and result
            # snapshot: flow directory
            local_storage.dump_snapshot(flow)
            # persist inputs, outputs and metrics
            local_storage.persist_result(batch_result)
            # exceptions
            local_storage.dump_exception(exception=exception, batch_result=batch_result)
            # system metrics
            system_metrics = {}
            if batch_result:
                system_metrics.update(batch_result.system_metrics.to_dict())  # token related
                system_metrics.update(
                    {f"{SystemMetricKeys.NODE_PREFIX}.{k}": v for k, v in batch_result.node_status.items()}
                )
                system_metrics.update(
                    {
                        SystemMetricKeys.LINES_COMPLETED: batch_result.completed_lines,
                        SystemMetricKeys.LINES_FAILED: batch_result.failed_lines,
                    }
                )

            run = self.run_operations.update(
                name=run.name,
                status=status,
                end_time=datetime.datetime.now().astimezone(),
                system_metrics=system_metrics,
            )

    def _resolve_input_dirs(self, run: Run):
        result = {"data": run.data if run.data else None}
        if run.run is not None:
            result.update(
                {
                    "run.outputs": self.run_operations._get_outputs_path(run.run),
                    # to align with cloud behavior, run.inputs should refer to original data
                    "run.inputs": self.run_operations._get_data_path(run.run),
                }
            )
        return {k: str(Path(v).resolve()) for k, v in result.items() if v is not None}

    @classmethod
    def _validate_column_mapping(cls, column_mapping: dict):
        if not column_mapping:
            return
        if not isinstance(column_mapping, dict):
            raise ValidationException(f"Column mapping must be a dict, got {type(column_mapping)}.")
        all_static = True
        for v in column_mapping.values():
            if isinstance(v, str) and v.startswith("$"):
                all_static = False
                break
        if all_static:
            raise ValidationException(
                "Column mapping must contain at least one mapping binding, "
                f"current column mapping contains all static values: {column_mapping}"
            )

    def _initialize_pfazure_client(self, run: Run, config=None):
        """Initialize pfazure client."""
        logger.debug("Initialize pfazure client to upload run to cloud...")
        from promptflow._sdk._tracing import _get_ws_triad_from_pf_config
        from promptflow.azure._cli._utils import _get_azure_pf_client

        ws_triad = _get_ws_triad_from_pf_config(path=run._get_flow_dir().resolve(), config=config or run._config)
        return _get_azure_pf_client(
            subscription_id=ws_triad.subscription_id,
            resource_group=ws_triad.resource_group_name,
            workspace_name=ws_triad.workspace_name,
        )

    def _initialize_async_run_uploader(self, run: Run, upload_to_cloud: bool):
        """Initialize async run uploader if upload_to_cloud is True."""
        uploader, pfazure_client = None, None
        if upload_to_cloud:
            logger.debug(f"Initialize async run uploader for run {run.name!r}...")
            from promptflow.azure.operations._async_run_uploader import AsyncRunUploader

            pfazure_client = self._initialize_pfazure_client(run=run, config=self._config)
            uploader = AsyncRunUploader._from_run_operations(run_ops=pfazure_client.runs)
        return uploader, pfazure_client
