import abc
import datetime
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow._utils.context_utils import _change_working_dir
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.executor._flow_nodes_scheduler import DEFAULT_CONCURRENCY_FLOW
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class FlowExecutorBase(abc.ABC):
    """This class includes the shared methods among executors cross different languages."""

    @classmethod
    @abc.abstractmethod
    def create(
        cls,
        flow_file: Path,
        connections: dict,
        working_dir: Optional[Path] = None,
        *,
        storage: Optional[AbstractRunStorage] = None,
        raise_ex: bool = True,
        node_override: Optional[Dict[str, Dict[str, Any]]] = None,
        line_timeout_sec: int = LINE_TIMEOUT_SEC,
    ) -> "FlowExecutorBase":
        pass

    @abc.abstractmethod
    def enable_streaming_for_llm_flow(self, stream_required: Callable[[], bool]):
        pass

    @abc.abstractmethod
    def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
        variant_id: str = "",
        validate_inputs: bool = True,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
        allow_generator_output: bool = False,
    ) -> LineResult:
        pass

    @abc.abstractmethod
    def exec_aggregation(
        self,
        inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id=None,
        node_concurrency=DEFAULT_CONCURRENCY_FLOW,
    ) -> AggregationResult:
        pass

    @classmethod
    @abc.abstractmethod
    def load_and_exec_node(
        cls,
        flow_file: Path,
        node_name: str,
        *,
        output_sub_dir: Optional[str] = None,
        flow_inputs: Optional[Mapping[str, Any]] = None,
        dependency_nodes_outputs: Optional[Mapping[str, Any]] = None,
        connections: Optional[dict] = None,
        working_dir: Optional[Path] = None,
        raise_ex: bool = False,
    ):
        pass


class CsharpExecutorProxy(AbstractExecutorProxy):
    def __init__(self, executor):
        self._executor = executor

    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""
        working_dir = working_dir or flow_file.parent

        from pythonnet import load

        # pythonnet.load must be called before import clr
        load("coreclr")
        import clr

        with _change_working_dir(working_dir):
            sys.path.append(working_dir.as_posix())
            clr.AddReference("Promptflow")
            sys.path.pop()
            from Promptflow.Executor import YamlExecutor

            connection_provider_url = ""
            executor = YamlExecutor(
                flow_file.read_text(encoding="utf-8"), connection_provider_url, working_dir.as_posix()
            )
            return cls(executor)

    def destroy(self):
        """Destroy the executor"""
        pass

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line"""
        start_time = datetime.datetime.now()
        from System import Object, String
        from System.Collections.Generic import Dictionary

        csharp_inputs = Dictionary[String, Object]()
        for key, value in inputs.items():
            csharp_inputs[key] = value
        task = self._executor.ExecuteAsync(csharp_inputs)
        task_result = task.Result

        output = {}
        for key in task_result.Keys:
            output[key] = task_result[key]
        return LineResult(
            output=output,
            aggregation_inputs={},
            node_run_infos={},
            run_info=FlowRunInfo(
                run_id="test",
                status=Status.Completed,
                error={},
                inputs=inputs,
                output=output,
                metrics={},
                request=None,
                parent_run_id="test",
                root_run_id="test",
                source_run_id="test",
                flow_id="test",
                start_time=start_time,
                end_time=datetime.datetime.now(),
            ),
        )

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return AggregationResult(output={}, metrics={}, node_run_infos={})

    @classmethod
    def generate_tool_metadata(cls, flow_dag: dict, working_dir: Path) -> dict:
        return {}
