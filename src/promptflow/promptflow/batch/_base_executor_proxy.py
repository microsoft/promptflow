from pathlib import Path
from typing import Any, Mapping, Optional

import httpx

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.exceptions import PromptflowException
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
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""
        raise NotImplementedError()

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
        raise NotImplementedError()

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        """Execute aggregation nodes"""
        raise NotImplementedError()


class APIBasedExecutorProxy(AbstractExecutorProxy):
    @property
    def api_endpoint(self) -> str:
        raise NotImplementedError()

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        url = self.api_endpoint + "/Execution"
        payload = {"run_id": run_id, "line_number": index, "inputs": inputs}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=LINE_TIMEOUT_SEC)
        response = self.process_http_response(response)
        return LineResult.deserialize(response)

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        async with httpx.AsyncClient() as client:
            url = self.api_endpoint + "/aggregation"
            payload = {"run_id": run_id, "batch_inputs": batch_inputs, "aggregation_inputs": aggregation_inputs}
            response = await client.post(url, json=payload, timeout=LINE_TIMEOUT_SEC)
        response = self.process_http_response(response)
        return AggregationResult.deserialize(response)

    def process_http_response(self, response: httpx.Response):
        status_code = response.status_code
        if status_code == 200:
            return response.json()
        else:
            # TODO: add more error handling
            raise PromptflowException(f"Error when calling executor API, response: {response}")
