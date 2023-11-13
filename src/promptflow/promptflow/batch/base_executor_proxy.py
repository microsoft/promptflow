from pathlib import Path
from typing import Any, List, Mapping, Optional

from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class AbstractExecutorProxy:
    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""
        raise NotImplementedError()

    def destroy(self):
        """Destroy the executor"""
        pass

    def exec_line(
        self, inputs: Mapping[str, Any], index: Optional[int] = None, run_id: Optional[str] = None
    ) -> LineResult:
        """Execute a line"""
        raise NotImplementedError()

    def exec_batch(self):
        pass

    def exec_aggregation(
        self,
        batch_inputs: List[dict],
        results: List[LineResult],
        run_id=None,
    ):
        pass


class APIBasedExecutorProxy(AbstractExecutorProxy):
    @property
    def api_endpoint(self) -> str:
        raise NotImplementedError()
