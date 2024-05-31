# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import inspect
import json
import os
from collections.abc import AsyncIterator, Iterator
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Union

from promptflow._constants import MessageFormatType
from promptflow._core._errors import FlowOutputUnserializable, RunRecordNotFound, ToolCanceledError
from promptflow._core.log_manager import NodeLogManager
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import flow_logger
from promptflow._utils.run_tracker_utils import _deep_copy_and_extract_items_from_generator_proxy
from promptflow._utils.utils import default_json_encoder
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.tool import ConnectionType
from promptflow.exceptions import ErrorTarget
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage, DummyRunStorage
from promptflow.tracing._openai_utils import OpenAIMetricsCalculator
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._thread_local_singleton import ThreadLocalSingleton
from promptflow.tracing._utils import serialize


class RunTracker(ThreadLocalSingleton):
    RUN_CONTEXT_NAME = "CurrentRun"
    CONTEXT_VAR_NAME = "RunTracker"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    @staticmethod
    def init_dummy() -> "RunTracker":
        return RunTracker(DummyRunStorage())

    def __init__(self, run_storage: AbstractRunStorage, run_mode: RunMode = RunMode.Test, node_log_manager=None):
        self._node_runs: Dict[str, RunInfo] = {}
        self._flow_runs: Dict[str, FlowRunInfo] = {}
        self._current_run_id = ""
        self._run_context = ContextVar(self.RUN_CONTEXT_NAME, default="")
        if run_storage is None:
            if self._skip_serialization_check():
                run_storage = DummyRunStorage()
            else:
                run_storage = DefaultRunStorage()
        self._storage = run_storage
        self._debug = True  # TODO: Make this configurable
        self.node_log_manager = node_log_manager or NodeLogManager()
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

    def set_current_run_in_context(self, run_id: str):
        self._run_context.set(run_id)

    def get_current_run_in_context(self) -> str:
        return self._run_context.get()

    def start_flow_run(
        self,
        flow_id,
        root_run_id,
        run_id,
        parent_run_id="",
        inputs=None,
        index=None,
        message_format=MessageFormatType.BASIC,
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
            message_format=message_format,
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
        message_format=MessageFormatType.BASIC,
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
            message_format=message_format,
        )
        self._node_runs[run_id] = run_info
        self._current_run_id = run_id
        self.set_current_run_in_context(run_id)
        self.node_log_manager.set_node_context(run_id, node, index)
        return run_info

    def bypass_node_run(
        self,
        node,
        flow_run_id,
        parent_run_id,
        run_id,
        index,
        message_format=MessageFormatType.BASIC,
    ):
        run_info = RunInfo(
            node=node,
            run_id=run_id,
            flow_run_id=flow_run_id,
            parent_run_id=parent_run_id,
            status=Status.Bypassed,
            inputs=None,
            output=None,
            metrics=None,
            error=None,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            result=None,
            index=index,
            api_calls=[],
            message_format=message_format,
        )
        self._node_runs[run_id] = run_info
        return run_info

    def _flow_run_postprocess(self, run_info: FlowRunInfo, output, ex: Optional[Exception]):
        #  Try get otel trace id for correlation.
        run_info.otel_trace_id = OperationContext.get_instance().get("otel_trace_id")
        if output:
            try:
                self._assert_flow_output_serializable(output)
            except Exception as e:
                output, ex = None, e
        self._common_postprocess(run_info, output, ex)

    def _update_flow_run_info_with_node_runs(self, run_info: FlowRunInfo):
        run_id = run_info.run_id
        child_run_infos = self.collect_child_node_runs(run_id)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(self.collect_metrics(child_run_infos, self.OPENAI_AGGREGATE_METRICS))
        # TODO: Refactor Tracer to support flow level tracing,
        # then we can remove the hard-coded root level api_calls here.
        # It has to be a list for UI backward compatibility.
        start_timestamp = run_info.start_time.astimezone(timezone.utc).timestamp() if run_info.start_time else None
        end_timestamp = run_info.end_time.astimezone(timezone.utc).timestamp() if run_info.end_time else None
        if self._skip_serialization_check():
            return
        # This implementation deep copies the inputs and output of the flow run, and extracts items from GeneratorProxy.
        # So that both image and generator will be supported.
        # It's a short term solution, while the long term one will be implemented in the next generation of Tracer.
        inputs = None
        output = None
        try:
            inputs = _deep_copy_and_extract_items_from_generator_proxy(run_info.inputs)
            output = _deep_copy_and_extract_items_from_generator_proxy(run_info.output)
        except Exception as e:
            flow_logger.warning(
                f"Failed to serialize inputs or output for flow run because of {e}."
                "The inputs and output field in api_calls will be None."
            )
        run_info.api_calls = [
            {
                "name": "flow",
                "node_name": "flow",
                "type": "Flow",
                "start_time": start_timestamp,
                "end_time": end_timestamp,
                "children": self._collect_traces_from_nodes(run_id),
                "system_metrics": run_info.system_metrics,
                "inputs": inputs,
                "output": output,
                "error": run_info.error,
            }
        ]

    def _node_run_postprocess(self, run_info: RunInfo, output, ex: Optional[Exception]):
        run_id = run_info.run_id
        if not inspect.isgenerator(output) and not inspect.isasyncgen(output):
            # Only set openai metrics for non-generator output.
            # For generator output, it will be set after the output is consumed.
            self.set_openai_metrics(run_id)
        logs = self.node_log_manager.get_logs(run_id)
        run_info.logs = logs
        self.node_log_manager.clear_node_context(run_id)

        if run_info.inputs:
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

    def cancel_node_runs(self, flow_run_id: Optional[str] = None, msg: str = "Received cancel request."):
        node_runs = self.collect_node_runs(flow_run_id)
        for node_run_info in node_runs:
            if node_run_info.status != Status.Running:
                continue
            msg = msg.rstrip(".")  # Avoid duplicated "." in the end of the message.
            err = ToolCanceledError(
                message_format="Tool execution is canceled because: {msg}.",
                msg=msg,
                target=ErrorTarget.EXECUTOR,
            )
            self.end_run(node_run_info.run_id, ex=err)
            node_run_info.status = Status.Canceled
            self.persist_node_run(node_run_info)

    def end_run(
        self,
        run_id: str,
        *,
        result: Optional[dict] = None,
        ex: Optional[Exception] = None,
        traces: Optional[List] = None,
    ):
        run_info = self._flow_runs.get(run_id) or self._node_runs.get(run_id)
        if run_info is None:
            raise RunRecordNotFound(
                message_format=(
                    "Run record with ID '{run_id}' was not tracked in promptflow execution. "
                    "Please contact support for further assistance."
                ),
                target=ErrorTarget.RUN_TRACKER,
                run_id=run_id,
            )
        # If the run is already canceled, do nothing.
        if run_info.status == Status.Canceled:
            return run_info
        if isinstance(run_info, FlowRunInfo):
            self._flow_run_postprocess(run_info, result, ex)
            if traces:
                run_info.api_calls = traces
        elif isinstance(run_info, RunInfo):
            run_info.api_calls = traces
            self._node_run_postprocess(run_info, result, ex)
        return run_info

    def _ensure_serializable_value(self, val, warning_msg: Optional[str] = None):
        if ConnectionType.is_connection_value(val):
            return ConnectionType.serialize_conn(val)
        if isinstance(val, (Iterator, AsyncIterator)):
            return str(val)
        if self._skip_serialization_check():
            return val
        try:
            json.dumps(val, default=default_json_encoder)
            return val
        except Exception:
            if not warning_msg:
                raise
            flow_logger.warning(warning_msg)
            return repr(val)

    @staticmethod
    def _skip_serialization_check():
        return os.getenv("PF_SKIP_SERIALIZATION_CHECK", "false").lower() == "true"

    def _ensure_inputs_is_json_serializable(self, inputs: dict, node_name: str) -> dict:
        return {
            k: self._ensure_serializable_value(
                v, f"Input '{k}' of {node_name} is not json serializable, use str to store it."
            )
            for k, v in inputs.items()
        }

    def _assert_flow_output_serializable(self, output: Any) -> Any:
        def _wrap_serializable_error(value):
            try:
                return self._ensure_serializable_value(value)
            except Exception as e:
                # If a specific key-value pair is not serializable, raise an exception with the key.
                error_type_and_message = f"({e.__class__.__name__}) {e}"
                message_format = (
                    "The output '{output_name}' for flow is incorrect. The output value is not JSON serializable. "
                    "JSON dump failed: {error_type_and_message}. Please verify your flow output and "
                    "make sure the value serializable."
                )
                raise FlowOutputUnserializable(
                    message_format=message_format,
                    target=ErrorTarget.FLOW_EXECUTOR,
                    output_name=k,
                    error_type_and_message=error_type_and_message,
                ) from e

        # support primitive outputs in eager mode
        if not isinstance(output, dict):
            return _wrap_serializable_error(output)
        serializable_output = {}
        for k, v in output.items():
            serializable_output[k] = _wrap_serializable_error(v)

        return serializable_output

    def _enrich_run_info_with_exception(self, run_info: Union[RunInfo, FlowRunInfo], ex: Exception):
        """Update exception details into run info."""
        # Update status to Cancelled the run terminates because of KeyboardInterruption or CancelledError.
        if isinstance(ex, KeyboardInterrupt) or isinstance(ex, asyncio.CancelledError):
            ex = ToolCanceledError(
                message_format="Tool execution is canceled because: {msg}.",
                msg="Received cancel request.",
                target=ErrorTarget.EXECUTOR,
            )
            run_info.status = Status.Canceled
        else:
            run_info.status = Status.Failed
        run_info.error = ExceptionPresenter.create(ex).to_dict(include_debug_info=self._debug)

    def collect_all_run_infos_as_dicts(self) -> Mapping[str, List[Mapping[str, Any]]]:
        flow_runs = self.flow_run_list
        node_runs = self.node_run_list
        return {
            "flow_runs": [serialize(run) for run in flow_runs],
            "node_runs": [serialize(run) for run in node_runs],
        }

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
                message_format=(
                    "Run record with ID '{run_id}' was not tracked in promptflow execution. "
                    "Please contact support for further assistance."
                ),
                target=ErrorTarget.RUN_TRACKER,
                run_id=run_id,
            )
        return run_info

    def set_inputs(self, run_id: str, inputs: Mapping[str, Any]):
        run_info = self.ensure_run_info(run_id)
        run_info.inputs = inputs

    def set_openai_metrics(self, run_id: str):
        # TODO: Provide a common implementation for different internal metrics
        run_info = self.ensure_run_info(run_id)
        calls = run_info.api_calls or []
        total_metrics = {}
        calculator = OpenAIMetricsCalculator(flow_logger)
        for call in calls:
            metrics = calculator.get_openai_metrics_from_api_call(call)
            calculator.merge_metrics_dict(total_metrics, metrics)
        run_info.system_metrics = run_info.system_metrics or {}
        run_info.system_metrics.update(total_metrics)

    def _collect_traces_from_nodes(self, run_id):
        child_run_infos = self.collect_child_node_runs(run_id)
        traces = []
        for node_run_info in child_run_infos:
            traces.extend(node_run_info.api_calls or [])
        return traces

    OPENAI_AGGREGATE_METRICS = ["prompt_tokens", "completion_tokens", "total_tokens"]

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

    def update_and_persist_generator_node_runs(self, run_id: str, node_names: List[str]):
        """
        Persists the node runs for nodes producing generators.

        :param run_id: The ID of the flow run.
        :type run_id: str
        :param node_names: The names of the nodes to persist.
        :type node_names: List[str]
        :returns: None
        """
        selected_node_run_info = (
            run_info for run_info in self.collect_child_node_runs(run_id) if run_info.node in node_names
        )
        for node_run_info in selected_node_run_info:
            if not node_run_info.api_calls:
                # Note that in some scenario (flow as function/serving), we don't have api_calls for the node run,
                # we don't need to update it.
                continue
            # Update the output of the node run with the output in the trace.
            # This is because the output in the trace would includes the generated items.
            output_in_trace = node_run_info.api_calls[0].get("output")
            node_run_info.output = output_in_trace
            # Update the openai metrics for the node run, since we can calculator the
            # completion tokens from the generated output.
            self.set_openai_metrics(node_run_info.run_id)
            # Persist the updated node run.
            self.persist_node_run(node_run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self._storage.persist_flow_run(run_info)

    def get_status_summary(self, run_id: str):
        node_run_infos = self.collect_node_runs(run_id)
        status_summary = {}

        for run_info in node_run_infos:
            node_name = run_info.node
            if run_info.index is not None:
                # Only consider Completed, Bypassed and Failed status, because the UX only support three status.
                if run_info.status in (Status.Completed, Status.Bypassed, Status.Failed):
                    node_status_key = f"__pf__.nodes.{node_name}.{run_info.status.value.lower()}"
                    status_summary[node_status_key] = status_summary.setdefault(node_status_key, 0) + 1
            # For reduce node, the index is None.
            else:
                status_summary[f"__pf__.nodes.{node_name}.completed"] = 1 if run_info.status == Status.Completed else 0

        # Runtime will start root flow run with run_id == root_run_id,
        # line flow run will have run id f"{root_run_id}_{line_number}"
        # We filter out root flow run accordingly.
        line_flow_run_infos = [
            flow_run_info
            for flow_run_info in self.flow_run_list
            if flow_run_info.root_run_id == run_id and flow_run_info.run_id != run_id
        ]
        total_lines = len(line_flow_run_infos)
        completed_lines = len(
            [flow_run_info for flow_run_info in line_flow_run_infos if flow_run_info.status == Status.Completed]
        )
        status_summary["__pf__.lines.completed"] = completed_lines
        status_summary["__pf__.lines.failed"] = total_lines - completed_lines
        return status_summary

    def persist_status_summary(self, status_summary: Dict[str, int], run_id: str):
        self._storage.persist_status_summary(status_summary, run_id)
