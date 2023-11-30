import multiprocessing
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import pytest

from promptflow._constants import FlowLanguage
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.contracts.run_info import Status
from promptflow.storage._run_storage import AbstractRunStorage

from ..mock_execution_server import run_executor_server
from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    def setup_method(self):
        BatchEngine.register_executor(FlowLanguage.CSharp, MockCSharpExecutorProxy)

    def test_batch(self):
        flow_folder = "csharp_flow"
        mem_run_storage = MemoryRunStorage()
        # init the batch engine
        batch_engine = BatchEngine(get_yaml_file(flow_folder), get_flow_folder(flow_folder), storage=mem_run_storage)
        # prepare the inputs
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        inputs_mapping = {"question": "${data.question}"}
        output_dir = Path(mkdtemp())
        # submit a batch run
        batch_result = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert batch_result.status == Status.Completed
        assert batch_result.completed_lines == batch_result.total_lines
        assert batch_result.system_metrics.duration > 0


class MockCSharpExecutorProxy(CSharpExecutorProxy):
    def __init__(self, process: multiprocessing.Process, port: str):
        self._process = process
        self._port = port

    @classmethod
    def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "MockCSharpExecutorProxy":
        """Create a new executor"""
        port = cls.find_available_port()
        process = multiprocessing.Process(target=run_executor_server, args=(port,))
        process.start()
        return cls(process, port)

    def destroy(self):
        """Destroy the executor"""
        if self._process and self._process.is_alive():
            self._process.terminate()
            try:
                self._process.join(timeout=5)
            except TimeoutError:
                self._process.kill()
