from pathlib import Path
from tempfile import mkdtemp
from typing import Optional

import pytest

from promptflow._constants import LINE_TIMEOUT_SEC, FlowLanguage
from promptflow.batch import BatchEngine, PythonExecutorProxy
from promptflow.batch._result import BatchResult, LineError
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.storage._run_storage import AbstractRunStorage

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
ONE_LINE_OF_BULK_TEST_TIMEOUT = "one_line_of_bulktest_timeout"


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatchTimeout:
    def setup_method(self):
        BatchEngine.register_executor(FlowLanguage.Python, MockPythonExecutorProxy)

    def teardown_method(self):
        BatchEngine.register_executor(FlowLanguage.Python, PythonExecutorProxy)

    @pytest.mark.parametrize(
        "flow_folder",
        [
            ONE_LINE_OF_BULK_TEST_TIMEOUT,
        ],
    )
    def test_batch_with_timeout(self, flow_folder, dev_connections):
        # set line timeout to 1 second for testing
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=mem_run_storage,
            line_timeout_sec=5,
        )
        # prepare input file and output dir
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="samples_all_timeout.json")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"idx": "${data.idx}"}
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert isinstance(batch_results, BatchResult)
        assert batch_results.completed_lines == 0
        assert batch_results.failed_lines == 2
        assert batch_results.total_lines == 2
        assert batch_results.node_status == {
            "my_python_tool_with_failed_line.canceled": 2,
            "my_python_tool.completed": 2,
        }

        # assert mem_run_storage persists run infos correctly
        assert len(mem_run_storage._flow_runs) == 2, "Flow runs are persisted in memory storage."
        assert len(mem_run_storage._node_runs) == 4, "Node runs are persisted in memory storage."
        msg = "Tool execution is canceled because of the error: Line execution timeout after 5 seconds."
        for run in mem_run_storage._node_runs.values():
            if run.node == "my_python_tool_with_failed_line":
                assert run.status == Status.Canceled
                assert run.error["message"] == msg
            else:
                assert run.status == Status.Completed
        assert batch_results.status == Status.Completed
        assert batch_results.total_lines == 2
        assert batch_results.completed_lines == 0
        assert batch_results.failed_lines == 2
        assert batch_results.error_summary.failed_user_error_lines == 2
        assert batch_results.error_summary.failed_system_error_lines == 0
        for i, line_error in enumerate(batch_results.error_summary.error_list):
            assert isinstance(line_error, LineError)
            assert line_error.error["message"] == f"Line {i} execution timeout for exceeding 5 seconds"
            assert line_error.error["code"] == "UserError"

    @pytest.mark.parametrize(
        "flow_folder",
        [
            ONE_LINE_OF_BULK_TEST_TIMEOUT,
        ],
    )
    def test_batch_with_one_line_timeout(self, flow_folder, dev_connections):
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=mem_run_storage,
            line_timeout_sec=5,
        )
        # set line timeout to 5 seconds for testing
        # prepare input file and output dir
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="samples.json")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"idx": "${data.idx}"}
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        assert isinstance(batch_results, BatchResult)
        # assert the line status in batch result
        assert batch_results.status == Status.Completed
        assert batch_results.total_lines == 3
        assert batch_results.completed_lines == 2
        assert batch_results.failed_lines == 1
        assert batch_results.node_status == {
            "my_python_tool_with_failed_line.completed": 2,
            "my_python_tool_with_failed_line.canceled": 1,
            "my_python_tool.completed": 3,
        }

        # assert the error summary in batch result
        assert batch_results.error_summary.failed_user_error_lines == 1
        assert batch_results.error_summary.failed_system_error_lines == 0
        assert isinstance(batch_results.error_summary.error_list[0], LineError)
        assert batch_results.error_summary.error_list[0].line_number == 2
        assert batch_results.error_summary.error_list[0].error["code"] == "UserError"
        assert (
            batch_results.error_summary.error_list[0].error["message"]
            == "Line 2 execution timeout for exceeding 5 seconds"
        )

        # assert mem_run_storage persists run infos correctly
        assert len(mem_run_storage._flow_runs) == 3, "Flow runs are persisted in memory storage."
        assert len(mem_run_storage._node_runs) == 6, "Node runs are persisted in memory storage."


class MockPythonExecutorProxy(PythonExecutorProxy):
    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "MockPythonExecutorProxy":
        line_timeout_sec = kwargs.get("line_timeout_sec", LINE_TIMEOUT_SEC)
        flow_executor = FlowExecutor.create(
            flow_file, connections, working_dir, storage=storage, raise_ex=False, line_timeout_sec=line_timeout_sec
        )
        return cls(flow_executor)
