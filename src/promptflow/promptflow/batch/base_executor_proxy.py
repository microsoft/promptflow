from pathlib import Path
from typing import Any, List, Mapping, Optional

import httpx

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.executor._result import AggregationResult, LineResult
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
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line"""
        raise NotImplementedError()

    def exec_aggregation(
        self,
        batch_inputs: List[dict],
        line_results: List[LineResult],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        pass


class APIBasedExecutorProxy(AbstractExecutorProxy):
    @property
    def api_endpoint(self) -> str:
        raise NotImplementedError()

    async def exec_line(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        async with httpx.AsyncClient() as client:
            payload = {"run_id": run_id, "line_number": index, "inputs": inputs}
            response = await client.post(self.api_endpoint, json=payload, timeout=LINE_TIMEOUT_SEC)
        # TODO: Implement LineResult deserialization
        return LineResult.deserialize(response.json())
