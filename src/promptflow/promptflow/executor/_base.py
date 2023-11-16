import abc
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.executor._flow_nodes_scheduler import DEFAULT_CONCURRENCY_FLOW
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage import AbstractRunStorage


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
