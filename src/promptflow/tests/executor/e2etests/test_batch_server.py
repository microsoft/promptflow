from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Mapping, Optional

import pytest
from fastapi.testclient import TestClient

from promptflow._constants import FlowLanguage
from promptflow._proxy import AbstractExecutorProxy, ProxyFactory
from promptflow._proxy._python_executor_proxy import PythonExecutorProxy
from promptflow.contracts.flow import FlowInputDefinition
from promptflow.contracts.run_info import Status
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor._service.app import app
from promptflow.storage import AbstractRunStorage

from ..utils import MemoryRunStorage, submit_batch_run


@pytest.mark.e2etest
class TestBatchServer:
    def test_batch_run_with_basic_flow(self):
        flow_folder = "print_input_flow"
        inputs_mapping = {"text": "${data.text}"}
        mem_run_storage = MemoryRunStorage()
        # Mock the executor proxy to use the test client
        ProxyFactory.register_executor(FlowLanguage.Python, MockPythonAPIBasedExecutorProxy)
        batch_result = submit_batch_run(
            flow_folder, inputs_mapping, input_file_name="inputs.jsonl", storage=mem_run_storage
        )
        assert batch_result.status == Status.Completed
        assert batch_result.total_lines == 10
        assert batch_result.completed_lines == batch_result.total_lines
        assert len(mem_run_storage._flow_runs) == 10
        assert len(mem_run_storage._node_runs) == 10
        # Reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor(FlowLanguage.Python, PythonExecutorProxy)

    def test_batch_run_with_image_flow(self):
        flow_folder = "eval_flow_with_simple_image"
        inputs_mapping = {"image": "${data.image}"}
        mem_run_storage = MemoryRunStorage()
        # Mock the executor proxy to use the test client
        ProxyFactory.register_executor(FlowLanguage.Python, MockPythonAPIBasedExecutorProxy)
        batch_result = submit_batch_run(
            flow_folder, inputs_mapping, input_file_name="inputs.jsonl", storage=mem_run_storage
        )
        assert batch_result.status == Status.Completed
        assert batch_result.total_lines == 2
        assert batch_result.completed_lines == batch_result.total_lines
        assert len(mem_run_storage._flow_runs) == 2
        assert len(mem_run_storage._node_runs) == 3
        # Reset the executor proxy to avoid affecting other tests
        ProxyFactory.register_executor(FlowLanguage.Python, PythonExecutorProxy)


class MockPythonAPIBasedExecutorProxy(AbstractExecutorProxy):
    def __init__(self, *, executor_client: TestClient, init_response: dict):
        super().__init__()
        self._executor_client = executor_client
        self._has_aggregation = init_response.get("has_aggregation", False)
        self._inputs_definition = init_response.get("inputs_definition", {})

    @property
    def has_aggregation(self):
        return self._has_aggregation

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        **kwargs,
    ) -> "MockPythonAPIBasedExecutorProxy":
        """Create a new executor"""
        executor_client = TestClient(app, raise_server_exceptions=False)
        output_dir = Path(mkdtemp())
        log_path = output_dir / "execution.log"
        request = {
            "working_dir": working_dir.as_posix(),
            "flow_file": flow_file.name,
            "connections": connections,
            "output_dir": output_dir.as_posix(),
            "log_path": log_path.as_posix(),
            "worker_count": worker_count,
            "line_timeout_sec": line_timeout_sec,
        }
        request = executor_client.post(url="/initialize", json=request)
        executor_proxy = cls(executor_client=executor_client, init_response=request.json())
        return executor_proxy

    async def destroy(self):
        """Destroy the executor"""
        return self._executor_client.post(url="/finalize")

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """Execute a line"""
        request = {"run_id": run_id, "line_number": index, "inputs": inputs}
        line_result = self._executor_client.post(url="/execution", json=request)
        return LineResult.deserialize(line_result.json())

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        """Execute aggregation nodes"""
        request = {"run_id": run_id, "batch_inputs": batch_inputs, "aggregation_inputs": aggregation_inputs}
        aggregation_result = self._executor_client.post(url="/aggregation", json=request)
        return AggregationResult.deserialize(aggregation_result.json())

    async def ensure_executor_health(self):
        """Ensure the executor service is healthy before execution"""
        return self._executor_client.get(url="/health")

    def get_inputs_definition(self):
        return {name: FlowInputDefinition.deserialize(i) for name, i in self._inputs_definition.items()}
