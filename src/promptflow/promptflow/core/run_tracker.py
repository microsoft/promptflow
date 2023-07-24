import json
from contextvars import ContextVar
from datetime import datetime
from types import GeneratorType
from typing import Any, Dict, List, Mapping, Optional, Union

from promptflow._constants import TOTAL_CHILD_RUNS_KEY, PromptflowEdition
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.tool import ConnectionType
from promptflow.contracts.trace import Trace, TraceType
from promptflow.core.log_manager import NodeLogManager
from promptflow.core.thread_local_singleton import ThreadLocalSingleton
from promptflow.exceptions import (
    ErrorResponse,
    ErrorTarget,
    ExceptionPresenter,
    RootErrorCode,
    RunInfoNotFoundInStorageError,
    UserErrorException,
    ValidationException,
)
from promptflow.storage import AbstractRunStorage
from promptflow.utils.dataclass_serializer import serialize
from promptflow.utils.logger_utils import flow_logger, logger
from promptflow.utils.utils import transpose


class RunTracker(ThreadLocalSingleton):
    RUN_CONTEXT_NAME = "CurrentRun"
    CONTEXT_VAR_NAME = "RunTracker"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    @staticmethod
    def init_from_env() -> "RunTracker":
        return RunTracker(AbstractRunStorage.init_from_env())

    @staticmethod
    def init_dummy() -> "RunTracker":
        return RunTracker(AbstractRunStorage.init_dummy())

    def __init__(self, run_storage: AbstractRunStorage, run_mode: RunMode = RunMode.Flow):
        self._node_runs: Dict[str, RunInfo] = {}
        self._flow_runs: Dict[str, FlowRunInfo] = {}
        self._current_run_id = ""
        self._run_context = ContextVar(self.RUN_CONTEXT_NAME, default="")
        self._storage = run_storage
        self._debug = True  # TODO: Make this configurable
        self.node_log_manager = NodeLogManager()
        self._has_failed_root_run = False
        self._run_mode = run_mode
        self._allow_generator_types = False

    @property
    def allow_generator_types(self):
        return self._allow_generator_types

    @allow_generator_types.setter
    def allow_generator_types(self, value: bool):
        self._allow_generator_types = value

    @property
    def node_run_list(self):
        # Add list() to make node_run_list a new list object,
        # therefore avoid iterating over a dictionary, which might be updated by another thread.
        return list(self._node_runs.values())

    @property
    def flow_run_list(self):
        # Add list() to make flow_run_list a new list object,
        # therefore avoid iterating over a dictionary, which might be updated by another thread.
        return list(self._flow_runs.values())

    @property
    def is_bulk_test(self):
        return self._run_mode == RunMode.BulkTest

    @property
    def should_upload_metrics(self):
        return self._run_mode in (RunMode.BulkTest, RunMode.Eval)

    @property
    def should_update_run_history(self):
        return (
            self._run_mode in (RunMode.BulkTest, RunMode.Eval)
            and self._storage._edition == PromptflowEdition.ENTERPRISE
        )

    def set_current_run_in_context(self, run_id: str):
        self._run_context.set(run_id)

    def get_current_run_in_context(self) -> str:
        return self._run_context.get()

    def _get_root_flow_run_from_storage(self, flow_id, root_run_id):
        """Try get root flow run from storage, return None if not found"""
        try:
            # Get run info and create if not exist.
            run_info: FlowRunInfo = self._storage.get_flow_run(root_run_id, flow_id)
        except RunInfoNotFoundInStorageError:
            return None
        return run_info

    def start_root_flow_run(
        self,
        flow_id,
        root_run_id,
        run_id,
        parent_run_id,
    ) -> FlowRunInfo:
        """Initialize the root flow run since it can be pre-created to storage before executor receives it."""
        run_info = self._get_root_flow_run_from_storage(flow_id=flow_id, root_run_id=root_run_id)
        if run_info is None:
            flow_logger.info(
                f"Root flow run not found in run storage {type(self._storage).__qualname__!r},"
                f" will create a new root flow run. Run id: {root_run_id!r}, flow id: {flow_id!r}"
            )
            run_info = self.start_flow_run(
                flow_id=flow_id, run_id=run_id, root_run_id=root_run_id, parent_run_id=parent_run_id
            )
        else:
            # Update status to started.
            run_info.start_time = datetime.utcnow()
            run_info.status = Status.Running
            if not run_info.parent_run_id:
                run_info.parent_run_id = parent_run_id

            self._storage.update_flow_run_info(run_info)
            flow_logger.info(
                f"Root flow run found in run storage {type(self._storage).__qualname__!r}. "
                f"Run id: {root_run_id!r}, flow id: {flow_id!r}."
            )

        # upload metrics is needed for only two run modes which are bulk test mode and evaluation mode,
        # and only for root flow runs.
        run_info.upload_metrics = self.should_upload_metrics
        self._flow_runs[root_run_id] = run_info
        self._current_run_id = root_run_id

        # start the root flow run that was created in azure machine learning workspace
        if self.should_update_run_history:
            self._storage._start_aml_root_run(run_id=run_id)

        return run_info

    def start_flow_run(
        self,
        flow_id,
        root_run_id,
        run_id,
        parent_run_id="",
        inputs=None,
        index=None,
        variant_id="",
    ) -> FlowRunInfo:
        """Create a flow run and save to run storage on demand."""
        run_info = FlowRunInfo(
            run_id=run_id,
            status=Status.Running,
            error=None,
            inputs=inputs,
            output=None,
            metrics=None,
            request=None,
            parent_run_id=parent_run_id,
            root_run_id=root_run_id,
            source_run_id=None,
            flow_id=flow_id,
            start_time=datetime.utcnow(),
            end_time=None,
            index=index,
            variant_id=variant_id,
        )
        self.persist_flow_run(run_info)
        self._flow_runs[run_id] = run_info
        self._current_run_id = run_id
        return run_info

    def start_node_run(
        self,
        node,
        flow_run_id,
        parent_run_id,
        run_id,
        index,
    ):
        run_info = RunInfo(
            node=node,
            run_id=run_id,
            flow_run_id=flow_run_id,
            status=Status.Running,
            inputs=None,
            output=None,
            metrics=None,
            error=None,
            parent_run_id=parent_run_id,
            start_time=datetime.utcnow(),
            end_time=None,
        )
        self._node_runs[run_id] = run_info
        self._current_run_id = run_id
        self.set_current_run_in_context(run_id)
        self.node_log_manager.set_node_context(run_id, node, index)
        return run_info

    def mark_notstarted_runs_as_failed(self, flow_id, root_run_ids, ex: Exception):
        """Handle run info update since root flow run can be created to storage before the executor receives
        the flow request
        """
        # No action needed for these two run modes
        if RunMode(self._run_mode) in (RunMode.SingleNode, RunMode.FromNode):
            return

        self._has_failed_root_run = True
        # for exceptions that raised before the flow is started, need to mark run failure and update the run info
        for root_run_id in root_run_ids:
            if root_run_id not in self._flow_runs:
                run_info = self._get_root_flow_run_from_storage(flow_id=flow_id, root_run_id=root_run_id)
                if run_info and run_info.status == Status.NotStarted:
                    self._flow_runs[root_run_id] = run_info
                    #  Make sure start_time is marked
                    run_info.start_time = run_info.start_time or datetime.utcnow()
                    self.end_run(run_id=root_run_id, ex=ex, update_at_last=True)
                    logger.info(f"Updated run {root_run_id!r} as failed in run info.")
                    # need to end the aml root runs for enterprise edition
                    if self.should_update_run_history:
                        self._storage._start_aml_root_run(run_id=root_run_id)
                        run_info.status = Status.Failed  # mark the status as Failed
                        self._storage._end_aml_root_run(run_info=run_info, ex=ex)
                        logger.info(f"Updated run {root_run_id!r} as failed in run history.")

    def mark_active_runs_as_failed_on_exit(self, root_run_ids, ex: Exception):
        """Mark active runs as failed on exit. This is useful to runtime shutdown gracefully."""
        # No action needed for these two run modes
        if RunMode(self._run_mode) in (RunMode.SingleNode, RunMode.FromNode):
            return

        logger.info("Updating active runs to failed on exit.")
        for root_run_id in root_run_ids:
            if root_run_id in self._flow_runs:
                run_info = self._flow_runs[root_run_id]
                if run_info.status == Status.Running:
                    run_info.status = Status.Failed
                    self.end_run(run_id=root_run_id, ex=ex, update_at_last=True)
                    logger.info(f"Updated run {root_run_id!r} as failed in run info.")
                    if self.should_update_run_history:
                        self._storage._end_aml_root_run(run_info=run_info, ex=ex)
                        logger.info(f"Updated run {root_run_id!r} as failed in run history.")

    def end_bulk_test_aml_run(self, bulk_test_id):
        # set the bulk test run as current active run
        self._storage._start_aml_root_run(run_id=bulk_test_id)
        # end the bulk run with status "Completed" for current implementation
        status_str = Status.Completed.value
        self._storage._end_aml_bulk_test_run(bulk_test_id=bulk_test_id, bulk_test_status=status_str)
        logger.info(f"Updated bulk test run {bulk_test_id!r} as {status_str} in run history.")

    def _flow_run_postprocess(self, run_info: FlowRunInfo, output, ex: Optional[Exception]):
        run_id = run_info.run_id
        is_root_flow_run = run_info.root_run_id == run_id
        if is_root_flow_run:
            # For root level flow run, it is actually the parent of the flow runs of all lines of data
            # it needs to collect all metrics from all lines.
            self.set_flow_metrics(run_id)
            # root run should also aggregate child run errors to root run's error
            if output is not None:
                self._aggregate_child_run_errors(run_info)
        else:
            # For sub flow run, it handles 1 line of data, it needs to collect metrics from the node runs,
            # it also needs to collect the traces from the node runs.
            self.set_parent_metrics(run_id)
            traces = self._collect_traces_from_nodes(run_id)
            run_info.api_calls = traces
        if output:
            try:
                self._assert_flow_output_serializable(output)
            except Exception as e:
                output, ex = None, e
        self._common_postprocess(run_info, output, ex)

    def _node_run_postprocess(self, run_info: RunInfo, output, ex: Optional[Exception]):
        run_id = run_info.run_id
        self.set_openai_metrics(run_id)
        logs = self.node_log_manager.get_logs(run_id)
        run_info.logs = logs
        self.node_log_manager.clear_node_context(run_id)

        run_info.inputs = self._ensure_inputs_is_json_serializable(run_info.inputs, run_info.node)
        if output is not None:
            msg = f"Output of {run_info.node} is not json serializable, use str to store it."
            output = self._ensure_serializable_value(output, msg)
        self._common_postprocess(run_info, output, ex)

    def _common_postprocess(self, run_info, output, ex):
        if output is not None:
            #  Duplicated fields for backward compatibility.
            run_info.result = output
            run_info.output = output
        if ex is not None:
            self._enrich_run_info_with_exception(run_info=run_info, ex=ex)
        else:
            run_info.status = Status.Completed
        run_info.end_time = datetime.utcnow()
        if not isinstance(run_info.start_time, datetime):
            flow_logger.warning(
                f"Run start time {run_info.start_time} for {run_info.run_id} is not a datetime object, "
                f"got {run_info.start_time}, type={type(run_info.start_time)}."
            )
        else:
            duration = (run_info.end_time - run_info.start_time).total_seconds()
            run_info.system_metrics = run_info.system_metrics or {}
            run_info.system_metrics["duration"] = duration

    def _aggregate_child_run_errors(self, root_run_info: FlowRunInfo):
        """Aggregate child run errors to root run's error.

        (Example)
            Base flow run (variant_0)
                Child run 0 (line data 0) -> Succeeded
                Child run 1 (line data 1) -> Failed by UserError/SubUserError
                Child run 2 (line data 2) -> Failed by SystemError/SubSystemError

            Root run's error messageFormat would be a json string of a dict:
            {
                "totalChildRuns": 3,
                "userErrorChildRuns": 1,
                "systemErrorChildRuns": 1,
                "errorDetails": [
                    {
                        "code": "UserError/SubUserError",
                        "messageFormat": "Sample user error message",
                        "count": 1
                    },
                    {
                        "code": "SystemError/SubSystemError",
                        "messageFormat": "Sample system error message",
                        "count": 1
                    }
                ]
            }

            So the full error response of this root run would be like:
            {
                "error": {
                    "code": "SystemError/SubSystemError",
                    "message": "I don't like banana!",
                    "messageFormat": '{"totalChildRuns": 3, "userErrorChildRuns": 1, "systemErrorChildRuns": 1, "errorDetails": [{"code": "UserError/SubUserError", "message": "Sample user error message", "count": 1}, {"code": "SystemError/SubSystemError", "message": "Sample user error message", "count": 1}]}',                     "message": '{"totalChildRuns": 3, "userErrorChildRuns": 1, "systemErrorChildRuns": 1, "errorDetails": [{"code": "UserError/SubUserError", "message": "Sample user error message", "count": 1}, {"code": "SystemError/SubSystemError", "message": "Sample user error message", "count": 1}]}',   # noqa: E501
                }
                "componentName": "promptflow/{runtime_version}"
            }

            Note that the message_format is the message_format of the first system error child run, if no such child run it
            is the error message_format of the first user error child run.

            messageFormat is a json string of aggregated child run error info.
        """
        # get all child runs info
        child_runs = self.collect_child_flow_runs(parent_run_id=root_run_info.run_id)
        child_runs = sorted(child_runs, key=lambda run_info: run_info.run_id)

        # calculate the number of user error and system error child runs
        user_error_child_runs = [
            run_info for run_info in child_runs if run_info.error and run_info.error["code"] == RootErrorCode.USER_ERROR
        ]
        system_error_child_runs = [
            run_info
            for run_info in child_runs
            if run_info.error and run_info.error["code"] == RootErrorCode.SYSTEM_ERROR
        ]
        error_details = {}

        # set root run error dict as first system or user error child run's error dict
        if user_error_child_runs:
            root_run_info.error = user_error_child_runs[0].error
        if system_error_child_runs:
            root_run_info.error = system_error_child_runs[0].error

        # aggregate child runs' errors, update root run error message
        for run_info in child_runs:
            error = run_info.error
            if error is None:
                continue

            # use error code and error message as key to aggregate
            error_key = error["code"] + error.get("messageFormat", "")
            if error_key not in error_details:
                error_details[error_key] = {
                    "code": ErrorResponse(error).error_code_hierarchy,
                    "messageFormat": error.get("messageFormat", ""),
                    "count": 1,
                }
            else:
                error_details[error_key]["count"] += 1

        # update root run error message with aggregated error details
        if error_details:
            # there is a hard limitation for writing run history error message which is 3000 characters
            # so we use "messageFormat" to store the full error message, the limitation for "messageFormat"
            # is between 1.6 million and 3.2 million characters
            root_run_info.error["messageFormat"] = json.dumps(
                {
                    "totalChildRuns": len(child_runs),
                    "userErrorChildRuns": len(user_error_child_runs),
                    "systemErrorChildRuns": len(system_error_child_runs),
                    "errorDetails": self._validate_error_details(list(error_details.values())),
                }
            )

    def _validate_error_details(self, error_list):
        """
        Make sure error details json string size is less than 1.6 million characters. Truncate the error detail
        to not exceed the limit if needed.
        """
        MAX_JSON_STRING_SIZE = 1600000
        while len(json.dumps(error_list)) > MAX_JSON_STRING_SIZE:
            old_length = len(error_list)
            new_length = old_length // 2
            error_list = error_list[:new_length]
            logger.warning(
                f"Error details json string size exceeds limit {MAX_JSON_STRING_SIZE!r}, "
                f"truncated error details item count from {old_length!r} to {new_length!r}."
            )

        return error_list

    def end_run(
        self,
        run_id: str,
        *,
        result: Optional[dict] = None,
        ex: Optional[Exception] = None,
        traces: Optional[List] = None,
        update_at_last: Optional[bool] = None,
    ):
        run_info = self._flow_runs.get(run_id) or self._node_runs.get(run_id)
        if run_info is None:
            raise RunRecordNotFound(message=f"Run {run_id} not found", target=ErrorTarget.RUN_TRACKER)
        if isinstance(run_info, FlowRunInfo):
            self._flow_run_postprocess(run_info, result, ex)
        elif isinstance(run_info, RunInfo):
            run_info.api_calls = traces
            self._node_run_postprocess(run_info, result, ex)

        # this could be used to determine bulk test aml run status or for other usages
        # currently we mark bulk test run as completed anyway.
        if run_info.status == Status.Failed and isinstance(run_info, FlowRunInfo) and run_id == run_info.root_run_id:
            self._has_failed_root_run = True

        if update_at_last is True and isinstance(run_info, FlowRunInfo):
            self.update_flow_run_info(run_info)

    def start_root_run_in_storage_for_prs(
        self,
        flow_id: str,
        run_id: str,
    ):
        """Update status and start time in PromptFlow backend storage.
        For PRS usage only.

        Args:
            flow_id (str): FlowId in PromptFlow
            run_id (str): RunId of the batch run
        """
        run_info = self._get_root_flow_run_from_storage(flow_id, run_id)
        if run_info is None:
            raise RunRecordNotFound(
                message=f"Record with flow_id: {flow_id}, run_id: {run_id} is not found", target=ErrorTarget.RUN_TRACKER
            )

        # Update status to started.
        run_info.start_time = datetime.utcnow()
        run_info.status = Status.Running

        self._storage.update_flow_run_info(run_info)

    def update_root_run_result_in_storage_for_prs(
        self, flow_id: str, run_id: str, results: Optional[list], ex: Optional[Exception] = None
    ):
        """Update bulk test output and metric or exception to root run.
        For PRS usage only.

        Args:
            flow_id (str): FlowId in PromptFlow
            run_id (str): RunId of the batch run
            results (list): list of single line flow result, each element is a dict containing key "flow_results".
            ex (Exception): Exception object if the PRS run failed due to initialization failure or other system error.
        """
        run_info = self._get_root_flow_run_from_storage(flow_id, run_id)
        # Put run info into memory to pass the validation in post process functions.
        self._flow_runs[run_id] = run_info
        if run_info is None:
            raise RunRecordNotFound(
                message=f"Record with flow_id: {flow_id}, run_id: {run_id} is not found", target=ErrorTarget.RUN_TRACKER
            )

        if not results:
            batch_results = []
        else:
            # Get output keys from the first result.
            output_keys = results[0].get("flow_results", {}).keys()
            batch_results = transpose([result.get("flow_results", {}) for result in results], keys=output_keys)

        self._flow_run_postprocess(run_info, batch_results, ex)
        self.update_flow_run_info(run_info)

    def _ensure_serializable_value(self, val, warning_msg: Optional[str] = None):
        if ConnectionType.is_connection_value(val):
            return ConnectionType.serialize_conn(val)
        if self.allow_generator_types and isinstance(val, GeneratorType):
            return str(val)
        try:
            json.dumps(val)
            return val
        except Exception:
            if not warning_msg:
                raise
            flow_logger.warning(warning_msg)
            return repr(val)

    def _ensure_inputs_is_json_serializable(self, inputs: dict, node_name: str) -> dict:
        return {
            k: self._ensure_serializable_value(
                v, f"Input '{k}' of {node_name} is not json serializable, use str to store it."
            )
            for k, v in inputs.items()
        }

    def _assert_flow_output_serializable(self, output: Any) -> Any:
        try:
            return self._ensure_serializable_value(output)
        except Exception as e:
            # If it is flow output not node output, raise an exception.
            raise UserErrorException(
                f"Flow output must be json serializable, dump json failed: {e}",
                target=ErrorTarget.FLOW_EXECUTOR,
            ) from e

    def _enrich_run_info_with_exception(self, run_info: Union[RunInfo, FlowRunInfo], ex: Exception):
        """Update exception details into run info."""
        run_info.error = ExceptionPresenter(ex).to_dict(include_debug_info=self._debug)
        run_info.status = Status.Failed

    def collect_all_run_infos_as_dicts(self) -> Mapping[str, List[Mapping[str, Any]]]:
        flow_runs = self.flow_run_list
        node_runs = self.node_run_list
        return {
            "flow_runs": [serialize(run) for run in flow_runs],
            "node_runs": [serialize(run) for run in node_runs],
        }

    def collect_flow_runs(self, root_run_id: str) -> List[FlowRunInfo]:
        return [run_info for run_info in self.flow_run_list if run_info.root_run_id == root_run_id]

    def collect_child_flow_runs(self, parent_run_id: str) -> List[FlowRunInfo]:
        return [run_info for run_info in self.flow_run_list if run_info.parent_run_id == parent_run_id]

    def collect_node_runs(self, flow_run_id: Optional[str] = None) -> List[RunInfo]:
        """If flow_run_id is None, return all node runs."""
        if flow_run_id:
            return [run_info for run_info in self.node_run_list if run_info.flow_run_id == flow_run_id]

        return [run_info for run_info in self.node_run_list]

    def collect_child_node_runs(self, parent_run_id: str) -> List[RunInfo]:
        return [run_info for run_info in self.node_run_list if run_info.parent_run_id == parent_run_id]

    def ensure_run_info(self, run_id: str) -> Union[RunInfo, FlowRunInfo]:
        run_info = self._node_runs.get(run_id) or self._flow_runs.get(run_id)
        if run_info is None:
            raise RunRecordNotFound(
                message=f"Run {run_id} not found when tracking inputs", target=ErrorTarget.RUN_TRACKER
            )
        return run_info

    def set_inputs(self, run_id: str, inputs: Mapping[str, Any]):
        run_info = self.ensure_run_info(run_id)
        run_info.inputs = inputs

    def log_metric(self, run_id: str, key: str, val: float, variant_id: Optional[str] = None):
        run_info = self.ensure_run_info(run_id)
        if run_info.metrics is None:
            run_info.metrics = {}
        if key not in run_info.metrics:
            run_info.metrics[key] = []
        item = {"value": val}
        if variant_id is not None:
            item["variant_id"] = variant_id
        run_info.metrics[key].append(item)

    def set_openai_metrics(self, run_id: str):
        # TODO: Provide a common implementation for different internal metrics
        run_info = self.ensure_run_info(run_id)
        calls = run_info.api_calls or []
        total_metrics = {}
        for call in calls:
            if call.get("type") != "LLM":
                continue
            call_output = call.get("output")
            if not isinstance(call_output, dict):
                # In some rare cases, the output is not a dict, e.g. when it uses streaming, it is a generator.
                continue
            run_metrics = call_output.get("usage")
            if not isinstance(run_metrics, dict):
                continue
            for k, v in run_metrics.items():
                total_metrics[k] = total_metrics.get(k, 0) + v
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(total_metrics)

    def _node_run_info_to_trace(self, run_info: RunInfo):
        return Trace(
            name=run_info.node,
            type=TraceType.TOOL,
            inputs=run_info.inputs,
            output=run_info.output,
            start_time=run_info.start_time.timestamp() if isinstance(run_info.start_time, datetime) else None,
            end_time=run_info.end_time.timestamp() if isinstance(run_info.end_time, datetime) else None,
            error=run_info.error,
            children=run_info.api_calls,
            node_name=run_info.node,
        )

    def _collect_traces_from_nodes(self, run_id):
        child_run_infos = self.collect_child_node_runs(run_id)
        traces = [self._node_run_info_to_trace(run_info) for run_info in child_run_infos]
        return traces

    OPENAI_AGGREGATE_METRICS = ["total_tokens"]

    def set_parent_metrics(self, run_id):
        run_info = self.ensure_run_info(run_id)
        if not isinstance(run_info, FlowRunInfo):
            return
        child_run_infos = self.collect_child_node_runs(run_id)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(self.collect_metrics(child_run_infos, self.OPENAI_AGGREGATE_METRICS))

    def set_flow_metrics(self, run_id):
        run_info = self.ensure_run_info(run_id)
        if not isinstance(run_info, FlowRunInfo):
            return
        node_run_infos = self.collect_node_runs(run_id)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(self.collect_metrics(node_run_infos, self.OPENAI_AGGREGATE_METRICS))

        # log line data child run numbers for root flow run, note the run_id must be a root run id
        child_runs = self.collect_child_flow_runs(run_id)
        run_info.system_metrics[TOTAL_CHILD_RUNS_KEY] = len(child_runs)

    def collect_metrics(self, run_infos: List[RunInfo], aggregate_metrics: List[str] = []):
        if not aggregate_metrics:
            return {}
        total_metrics = {}
        for run_info in run_infos:
            if not run_info.system_metrics:
                continue
            for metric in aggregate_metrics:
                total_metrics[metric] = total_metrics.get(metric, 0) + run_info.system_metrics.get(metric, 0)
        return total_metrics

    def get_run(self, run_id):
        return self._node_runs.get(run_id) or self._flow_runs.get(run_id)

    def persist_node_run(self, run_info: RunInfo):
        self._storage.persist_node_run(run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._storage.persist_flow_run(run_info)

    def update_flow_run_info(self, run_info: FlowRunInfo):
        """This operation only updates the flow run info related fields."""
        self._storage.update_flow_run_info(run_info)

    def get_status_summary(self, run_id: str):
        node_run_infos = self.collect_node_runs(run_id)
        status_summary = {}
        line_status = {}
        for run_info in node_run_infos:
            if run_info.index is not None:
                if run_info.index not in line_status.keys():
                    line_status[run_info.index] = True

                line_status[run_info.index] = line_status[run_info.index] and run_info.status == Status.Completed

                node_name = run_info.node
                if "nodes." + node_name + ".completed" not in status_summary.keys():
                    status_summary["nodes." + node_name + ".completed"] = 0
                    status_summary["nodes." + node_name + ".failed"] = 0

                # Only consider Completed and Failed status, because the UX only support two status.
                if run_info.status in (Status.Completed, Status.Failed):
                    status_summary["nodes." + node_name + f".{run_info.status.value}".lower()] += 1

            # For reduce node, the index is None.
            else:
                node_name = run_info.node
                status_summary["nodes." + node_name + ".completed"] = 1 if run_info.status == Status.Completed else 0

        status_summary["lines.completed"] = sum(line_status.values())
        status_summary["lines.failed"] = len(line_status) - status_summary["lines.completed"]
        return status_summary

    def persist_status_summary(self, status_summary: Dict[str, int], run_id: str):
        self._storage.persist_status_summary(status_summary, run_id)


def log_metric(key, value, variant_id=None):
    run_tracker = RunTracker.active_instance()
    run_id = run_tracker.get_current_run_in_context() if run_tracker else None
    if not run_id:
        logger.warning(f"Cannot log metric {key}={value} because no run is active")
        return
    run_info = run_tracker.get_run(run_id)
    if not isinstance(run_info, RunInfo):
        logger.warning(f"Cannot log metric {key}={value} because run {run_id} is not a node run")
        return
    flow_run_info = run_tracker.get_run(run_info.parent_run_id)
    if not isinstance(flow_run_info, FlowRunInfo):
        parent_run_id = run_info.parent_run_id
        logger.warning(f"Cannot log metric {key}={value} because {run_id}'s parent {parent_run_id} is not a flow run")
        return
    if flow_run_info.root_run_id != flow_run_info.run_id:
        msg = f"Only aggregation node can log metrics. Please make sure '{run_info.node}' is an aggregation node."
        raise NodeTypeNotsupportedForLoggingMetric(message=msg, target=ErrorTarget.TOOL)
    if variant_id and not isinstance(variant_id, str):
        messgae = f"variant_id must be a string, got {variant_id} of type {type(variant_id)}"
        raise VariantIdTypeError(message=messgae, target=ErrorTarget.TOOL)
    try:
        value = float(value)
    except (TypeError, ValueError) as e:
        logger.warning(
            f"Cannot log metric because the value is not a number. Metric {key}={value} of type {type(value)}"
        )
        logger.warning(str(e))
        #  Currently this is just for backward compatibility. We should remove this in the future.
        return
    run_tracker.log_metric(flow_run_info.run_id, key, value, variant_id=variant_id)


class RunRecordNotFound(ValidationException):
    pass


class NodeTypeNotsupportedForLoggingMetric(ValidationException):
    pass


class VariantIdTypeError(ValidationException):
    pass
