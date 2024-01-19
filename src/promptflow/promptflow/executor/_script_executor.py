import asyncio
import inspect
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool_meta_generator import PythonLoadError, load_python_module_from_file
from promptflow._core.tracer import Tracer, _traced
from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_mode import RunMode
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage

from .flow_executor import FlowExecutor


class ScriptExecutor(FlowExecutor):
    def __init__(
        self,
        entry_file: Path,
        func: Optional[str],
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
    ):
        logger.debug("Start initializing the executor with {entry_file}.")
        working_dir = Flow._resolve_working_dir(entry_file, working_dir)
        m = load_python_module_from_file(entry_file)
        self._func: Callable = getattr(m, str(func), None)
        if self._func is None or not inspect.isfunction(self._func):
            raise PythonLoadError(
                message_format="Failed to load python function '{func}' from file '{entry_file}'.",
                entry_file=entry_file,
                func=func,
            )
        self._is_async = inspect.iscoroutinefunction(self._func)
        # If the function is not decorated with trace, add trace for it.
        if not hasattr(self._func, "__original_function"):
            self._func = _traced(self._func)
        self._storage = storage or DefaultRunStorage()

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        **kwargs,
    ) -> LineResult:
        operation_context = OperationContext.get_instance()
        operation_context.run_mode = operation_context.get("run_mode", None) or RunMode.Test.name
        run_id = run_id or str(uuid.uuid4())
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        run_tracker = RunTracker(self._storage)
        default_flow_id = "default_flow_id"
        run_info = run_tracker.start_flow_run(
            flow_id=default_flow_id,
            root_run_id=run_id,
            run_id=line_run_id,
            parent_run_id=run_id,
            inputs=inputs,
            index=index,
        )
        output = {}
        traces = []
        try:
            Tracer.start_tracing(line_run_id)
            if self._is_async:
                output = asyncio.run(self._func(**inputs))
            else:
                output = self._func(**inputs)
            traces = Tracer.end_tracing(line_run_id)
            run_tracker.end_run(line_run_id, result=output, traces=traces)
        except Exception as e:
            if not traces:
                traces = Tracer.end_tracing(line_run_id)
            run_tracker.end_run(line_run_id, ex=e, traces=traces)
        finally:
            run_tracker.persist_flow_run(run_info)
        line_result = LineResult(output, {}, run_info, {})
        #  Return line result with index
        if index is not None and isinstance(line_result.output, dict):
            line_result.output[LINE_NUMBER_KEY] = index
        return line_result

    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        # TODO(2901157): check if eager mode should have streaming
        return
