import asyncio
import importlib
import inspect
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._core.run_tracker import RunTracker
from promptflow._core.tool_meta_generator import PythonLoadError
from promptflow._core.tracer import Tracer, _traced
from promptflow._utils.dataclass_serializer import convert_eager_flow_output_to_dict
from promptflow._utils.logger_utils import logger
from promptflow._utils.tool_utils import function_to_interface
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.flow import Flow
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage

from .flow_executor import FlowExecutor


class ScriptExecutor(FlowExecutor):
    def __init__(
        self,
        flow_file: Path,
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
    ):
        logger.debug(f"Start initializing the executor with {flow_file}.")

        self._flow_file = flow_file
        self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        self._initialize_function()
        self._connections = connections
        self._storage = storage or DefaultRunStorage()
        self._flow_id = "default_flow_id"
        self._log_interval = 60
        self._line_timeout_sec = 600

    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        **kwargs,
    ) -> LineResult:
        run_id = run_id or str(uuid.uuid4())
        with self._update_operation_context(run_id):
            return self._exec_line(inputs, index, run_id)

    def _exec_line(
        self, inputs: Mapping[str, Any], index: Optional[int] = None, run_id: Optional[str] = None
    ) -> LineResult:
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        run_tracker = RunTracker(self._storage)
        run_info = run_tracker.start_flow_run(
            flow_id=self._flow_id,
            root_run_id=run_id,
            run_id=line_run_id,
            parent_run_id=run_id,
            inputs=inputs,
            index=index,
        )
        # Executor will add line_number to batch inputs if there is no line_number in the original inputs,
        # which should be removed, so, we only preserve the inputs that are contained in self._inputs.
        inputs = {k: inputs[k] for k in self._inputs if k in inputs}
        output = None
        traces = []
        try:
            Tracer.start_tracing(line_run_id)
            if self._is_async:
                output = asyncio.run(self._func(**inputs))
            else:
                output = self._func(**inputs)
            traces = Tracer.end_tracing(line_run_id)
            # Should convert output to dict before storing it to run info, since we will add key 'line_number' to it,
            # so it must be a dict.
            output_dict = convert_eager_flow_output_to_dict(output)
            run_tracker.end_run(line_run_id, result=output_dict, traces=traces)
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

    def get_inputs_definition(self):
        return self._inputs

    def _initialize_function(self):
        module_name, func_name = self._parse_flow_file()
        module = importlib.import_module(module_name)
        func = getattr(module, func_name, None)
        if func is None or not inspect.isfunction(func):
            raise PythonLoadError(
                message_format="Failed to load python function '{func_name}' from file '{module_name}'.",
                func_name=func_name,
                module_name=module_name,
            )
        # If the function is not decorated with trace, add trace for it.
        if not hasattr(func, "__original_function"):
            func = _traced(func)
        self._func = func
        inputs, _, _, _ = function_to_interface(self._func)
        self._inputs = {k: v.to_flow_input_definition() for k, v in inputs.items()}
        self._is_async = inspect.iscoroutinefunction(self._func)
        return func

    def _parse_flow_file(self):
        with open(self._working_dir / self._flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        entry = flow_dag.get("entry", "")
        module_name, func_name = entry.split(":")
        return module_name, func_name
