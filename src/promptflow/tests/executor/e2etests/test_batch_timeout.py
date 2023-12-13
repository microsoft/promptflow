from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.batch import BatchEngine
from promptflow.batch._result import BatchResult, LineError
from promptflow.contracts.run_info import Status

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file

SAMPLE_FLOW = "web_classification_no_variants"
ONE_LINE_OF_BULK_TEST_TIMEOUT = "one_line_of_bulktest_timeout"


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestBatchTimeout:
    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_batch_with_timeout(self, flow_folder, dev_connections):
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        # set line timeout to 1 second for testing
        batch_engine._executor_proxy._flow_executor._line_timeout_sec = 1
        # prepare input file and output dir
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="samples.json")}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"url": "${data.url}"}
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert isinstance(batch_results, BatchResult)

        assert batch_results.status == Status.Completed
        assert batch_results.total_lines == 2
        assert batch_results.completed_lines == 0
        assert batch_results.failed_lines == 2
        assert batch_results.error_summary.failed_user_error_lines == 2
        assert batch_results.error_summary.failed_system_error_lines == 0
        for i, line_error in enumerate(batch_results.error_summary.line_error_list):
            assert isinstance(line_error, LineError)
            assert line_error.error["message"] == f"Line {i} execution timeout for exceeding 1 seconds"
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
        # set line timeout to 1 second for testing
        batch_engine._executor_proxy._flow_executor._line_timeout_sec = 60
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

        # assert the error summary in batch result
        assert batch_results.error_summary.failed_user_error_lines == 1
        assert batch_results.error_summary.failed_system_error_lines == 0
        assert isinstance(batch_results.error_summary.line_error_list[0], LineError)
        assert batch_results.error_summary.line_error_list[0].line_number == 2
        assert batch_results.error_summary.line_error_list[0].error["code"] == "UserError"
        assert (
            batch_results.error_summary.line_error_list[0].error["message"]
            == "Line 2 execution timeout for exceeding 60 seconds"
        )

        # assert mem_run_storage persists run infos correctly
        assert len(mem_run_storage._flow_runs) == 3, "Flow run is not persisted in memory storage."
        assert len(mem_run_storage._node_runs) == 5, "Node run is not persisted in memory storage."
