import json
import multiprocessing
import threading
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional, Tuple, Union

import pytest

from promptflow._constants import FlowLanguage
from promptflow._proxy import ProxyFactory
from promptflow._proxy._csharp_executor_proxy import CSharpExecutorProxy
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, ValidationException
from promptflow.executor._errors import GetConnectionError
from promptflow.storage._run_storage import AbstractRunStorage

from ..mock_execution_server import run_executor_server
from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file


@pytest.mark.unittest
class TestCSharpExecutorProxy:
    def setup_method(self):
        ProxyFactory.register_executor(FlowLanguage.CSharp, MockCSharpExecutorProxy)

    def teardown_method(self):
        del ProxyFactory.executor_proxy_classes[FlowLanguage.CSharp]

    def test_batch(self):
        # submit a batch run
        _, batch_result = self._submit_batch_run()
        assert batch_result.status == Status.Completed
        assert batch_result.completed_lines == batch_result.total_lines
        assert batch_result.system_metrics.duration > 0
        assert batch_result.completed_lines > 0

    def test_batch_execution_error(self):
        # submit a batch run
        _, batch_result = self._submit_batch_run(has_error=True)
        assert batch_result.status == Status.Completed
        assert batch_result.total_lines == 3
        assert batch_result.failed_lines == 1
        assert batch_result.system_metrics.duration > 0

    def test_batch_validation_error(self):
        # prepare the init error file to mock the validation error
        test_exception = GetConnectionError(connection="test_connection", node_name="mock", error=Exception("mock"))
        error_dict = ExceptionPresenter.create(test_exception).to_dict()
        init_error_file = Path(mkdtemp()) / "init_error.json"
        with open(init_error_file, "w") as file:
            json.dump(error_dict, file)
        # submit a batch run
        with pytest.raises(ValidationException) as e:
            self._submit_batch_run(init_error_file=init_error_file)
        assert "Get connection 'test_connection' for node 'mock' error: mock" in e.value.message
        assert e.value.error_codes == ["UserError", "ValidationError"]
        assert e.value.target == ErrorTarget.BATCH

    def test_batch_cancel(self):
        # use a thread to submit a batch run
        batch_engine, batch_run_thread = self._submit_batch_run(run_in_thread=True)
        assert batch_engine._is_canceled is False
        batch_run_thread.start()
        # cancel the batch run
        batch_engine.cancel()
        batch_run_thread.join()
        assert batch_engine._is_canceled is True
        assert batch_result_global.status == Status.Canceled
        assert batch_result_global.system_metrics.duration > 0

    def _submit_batch_run(
        self, run_in_thread=False, has_error=False, init_error_file=None
    ) -> Union[Tuple[BatchEngine, threading.Thread], Tuple[BatchEngine, BatchResult]]:
        flow_folder = "csharp_flow"
        mem_run_storage = MemoryRunStorage()
        # init the batch engine
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            storage=mem_run_storage,
            has_error=has_error,
            init_error_file=init_error_file,
        )
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
        super().__init__(
            process=process,
            port=port,
        )

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "MockCSharpExecutorProxy":
        """Create a new executor"""
        has_error = kwargs.get("has_error", False)
        init_error_file = kwargs.get("init_error_file", None)
        port = cls.find_available_port()
        process = multiprocessing.Process(
            target=run_executor_server,
            args=(
                int(port),
                has_error,
                init_error_file,
            ),
        )
        process.start()
        executor_proxy = cls(process, port)
        await executor_proxy.ensure_executor_startup(init_error_file)
        return executor_proxy

    async def destroy(self):
        """Destroy the executor"""
        if self._process and self._process.is_alive():
            self._process.terminate()
            try:
                self._process.join(timeout=5)
            except TimeoutError:
                self._process.kill()

    def _is_executor_active(self):
        return self._process and self._process.is_alive()
