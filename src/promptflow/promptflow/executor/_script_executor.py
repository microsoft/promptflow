import asyncio
import inspect
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool_meta_generator import PythonLoadError, load_python_module_from_file
from promptflow._core.tracer import _traced, Tracer
from promptflow._utils.logger_utils import logger
from promptflow._utils.tool_utils import function_to_interface
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_mode import RunMode
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage

from .flow_executor import FlowExecutor


class ScriptExecutor(FlowExecutor):
    def __init__(
        self,
        flow_file: Path,
        entry: str,
        connections: dict,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
    ):
        logger.debug(f"Start initializing the executor with {flow_file}.")
        self._flow_file = flow_file

        m = load_python_module_from_file(flow_file)
        func: Callable = getattr(m, entry, None)
        if func is None or not inspect.isfunction(func):
            raise PythonLoadError(
                message_format="Failed to load python function '{entry}' from file '{flow_file}'.",
                entry=entry,
                flow_file=flow_file,
            )
        # If the function is not decorated with trace, add trace for it.
        if not hasattr(func, "__original_function"):
            func = _traced(func)
        inputs, _, _, _ = function_to_interface(func)
        self._func = func
        self._inputs = inputs

        self._entry = entry
        self._is_async = inspect.iscoroutinefunction(self._func)
        self._connections = connections
        self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        # TODO: Remove run track from executor
        self._run_tracker = RunTracker(storage or DefaultRunStorage())
        self._flow_id = None
        self._log_interval = 60
        self._line_timeout_sec = 600

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        **kwargs,
    ) -> LineResult:
        # Executor will add line_number to batch inputs if there is no line_number in the original inputs,
        # so, we need remove line_number from inputs if it is not included in input of python function.
        if "line_number" in inputs and "line_number" not in self._inputs:
            inputs.pop("line_number")
        operation_context = OperationContext.get_instance()
        operation_context.run_mode = operation_context.get("run_mode", None) or RunMode.Test.name
        run_id = run_id or str(uuid.uuid4())
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        default_flow_id = "default_flow_id"
        run_info = self._run_tracker.start_flow_run(
            flow_id=default_flow_id,
            root_run_id=run_id,
            run_id=line_run_id,
            parent_run_id=run_id,
            inputs=inputs,
            index=index,
        )
        traces = []
        try:
            Tracer.start_tracing(line_run_id)
            if self._is_async:
                output = asyncio.run(self._func(**inputs))
            else:
                output = self._func(**inputs)
            output = {"output": output}
            traces = Tracer.end_tracing(line_run_id)
            self._run_tracker.end_run(line_run_id, result=output, traces=traces)
        except Exception as e:
            if not traces:
                traces = Tracer.end_tracing(line_run_id)
            self._run_tracker.end_run(line_run_id, ex=e, traces=traces)
        finally:
            self._run_tracker.persist_flow_run(run_info)
        line_result = LineResult(output, {}, run_info, {})
        #  Return line result with index
        if index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = index
        return line_result

    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        # TODO(2901157): check if eager mode should have streaming
        return
