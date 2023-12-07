import asyncio
import multiprocessing
import threading
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional, Tuple, Union

import pytest

from promptflow._constants import FlowLanguage
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.storage._run_storage import AbstractRunStorage

from ..mock_execution_server import run_executor_server
from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    def setup_method(self):
        BatchEngine.register_executor(FlowLanguage.CSharp, MockCSharpExecutorProxy)

    def test_batch(self):
        # submit a batch run
        _, batch_result = self._submit_batch_run()
        assert batch_result.status == Status.Completed
        assert batch_result.completed_lines == batch_result.total_lines
        assert batch_result.system_metrics.duration > 0
        assert batch_result.completed_lines > 0

    @pytest.mark.asyncio
    async def test_batch_cancel(self):
        # use a thread to submit a batch run
        batch_engine, batch_run_thread = self._submit_batch_run(run_in_thread=True)
        assert batch_engine._is_canceled is False
        batch_run_thread.start()
        # cancel the batch run
        await asyncio.sleep(5)
        batch_engine.cancel()
        batch_run_thread.join()
        assert batch_engine._is_canceled is True
        assert batch_result_global.status == Status.Canceled
        assert batch_result_global.system_metrics.duration > 0
        assert batch_result_global.total_lines > 0

    def _submit_batch_run(
        self, run_in_thread=False
    ) -> Union[Tuple[BatchEngine, threading.Thread], Tuple[BatchEngine, BatchResult]]:
        flow_folder = "csharp_flow"
        mem_run_storage = MemoryRunStorage()
        # init the batch engine
        batch_engine = BatchEngine(get_yaml_file(flow_folder), get_flow_folder(flow_folder), storage=mem_run_storage)
        # prepare the inputs
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        inputs_mapping = {"question": "${data.question}"}
        output_dir = Path(mkdtemp())
        if run_in_thread:
            return batch_engine, threading.Thread(
                target=self._batch_run_in_thread, args=(batch_engine, input_dirs, inputs_mapping, output_dir)
            )
        else:
            return batch_engine, batch_engine.run(input_dirs, inputs_mapping, output_dir)

    def _batch_run_in_thread(self, batch_engine: BatchEngine, input_dirs, inputs_mapping, output_dir):
        global batch_result_global
        batch_result_global = batch_engine.run(input_dirs, inputs_mapping, output_dir)


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
        process = multiprocessing.Process(target=run_executor_server, args=(int(port),))
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
