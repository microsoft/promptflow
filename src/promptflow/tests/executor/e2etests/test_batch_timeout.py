from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow.batch import BatchEngine
from promptflow.batch._errors import BatchRunTimeoutError
from promptflow.batch._result import BatchResult, LineError
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import BatchExecutionTimeoutError, LineExecutionTimeoutError

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
ONE_LINE_OF_BULK_TEST_TIMEOUT = "one_line_of_bulktest_timeout"


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatchTimeout:
    @pytest.mark.parametrize(
        "flow_folder",
        [
            ONE_LINE_OF_BULK_TEST_TIMEOUT,
        ],
    )
    def test_batch_with_line_timeout(self, flow_folder, dev_connections):
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=mem_run_storage,
        )
        # set line timeout to 5 seconds for testing
        batch_engine._line_timeout_sec = 5
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
        )
        batch_engine._line_timeout_sec = 5
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
        assert batch_results.error_summary.error_list[0].error["referenceCode"] == "Executor"
        assert batch_results.error_summary.error_list[0].error["innerError"]["code"] == "LineExecutionTimeoutError"
        assert (
            batch_results.error_summary.error_list[0].error["message"]
            == "Line 2 execution timeout for exceeding 5 seconds"
        )

        # assert mem_run_storage persists run infos correctly
        assert len(mem_run_storage._flow_runs) == 3, "Flow runs are persisted in memory storage."
        assert len(mem_run_storage._node_runs) == 6, "Node runs are persisted in memory storage."

    @pytest.mark.parametrize(
        "flow_folder, line_timeout_sec, batch_timeout_sec, expected_error, batch_run_status",
        [
            (ONE_LINE_OF_BULK_TEST_TIMEOUT, 600, 5, BatchExecutionTimeoutError(2, 5), Status.Failed),
            (ONE_LINE_OF_BULK_TEST_TIMEOUT, 3, 600, LineExecutionTimeoutError(2, 3), Status.Completed),
            (ONE_LINE_OF_BULK_TEST_TIMEOUT, 10, 10, BatchExecutionTimeoutError(2, 10), Status.Failed),
        ],
    )
    def test_batch_timeout(self, flow_folder, line_timeout_sec, batch_timeout_sec, expected_error, batch_run_status):
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections={},
            storage=mem_run_storage,
        )
        batch_engine._line_timeout_sec = line_timeout_sec
        batch_engine._batch_timeout_sec = batch_timeout_sec

        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="samples.json")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"idx": "${data.idx}"}
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        assert isinstance(batch_results, BatchResult)
        # assert the line status in batch result
        assert batch_results.status == batch_run_status
        assert batch_results.total_lines == 3
        assert batch_results.completed_lines == 2
        assert batch_results.failed_lines == 1
        assert batch_results.node_status == {
            "my_python_tool_with_failed_line.completed": 2,
            "my_python_tool_with_failed_line.canceled": 1,
            "my_python_tool.completed": 3,
        }

        # assert the error summary in batch result
        if batch_run_status == Status.Failed:
            ex = BatchRunTimeoutError(
                message="The batch run failed due to timeout. Please adjust the timeout settings to a higher value.",
                target=ErrorTarget.BATCH,
            )
            assert batch_results.error_summary.batch_error_dict == ExceptionPresenter.create(ex).to_dict()
        assert batch_results.error_summary.failed_user_error_lines == 1
        assert batch_results.error_summary.failed_system_error_lines == 0

        actual_line_error = batch_results.error_summary.error_list[0]
        assert isinstance(actual_line_error, LineError)
        assert actual_line_error.line_number == 2
        actual_error_dict = actual_line_error.error
        expected_error_dict = ExceptionPresenter.create(expected_error).to_dict()
        assert actual_error_dict["code"] == expected_error_dict["code"]
        assert actual_error_dict["message"] == expected_error_dict["message"]
        assert actual_error_dict["referenceCode"] == expected_error_dict["referenceCode"]
        assert actual_error_dict["innerError"]["code"] == expected_error_dict["innerError"]["code"]

        # assert mem_run_storage persists run infos correctly
        assert len(mem_run_storage._flow_runs) == 3, "Flow runs are persisted in memory storage."
        # TODO: Currently, the node status is incomplete.
        # We will assert the correct result after refining the implementation of batch timeout.
        assert len(mem_run_storage._node_runs) == 6, "Node runs are persisted in memory storage."
