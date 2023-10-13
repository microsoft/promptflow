import re
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.exception_utils import ErrorResponse
from promptflow._utils.logger_utils import LogContext
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.executor._flow_nodes_scheduler import RUN_FLOW_NODES_LINEARLY
from promptflow.executor.flow_executor import FlowExecutor, LineResult

from ..utils import get_flow_inputs, get_yaml_file, load_content

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_ROOT = TEST_ROOT / "test_configs/flows"
FLOW_FOLDER = "concurrent_execution_flow"


@pytest.mark.e2etest
class TestConcurrentExecution:
    def test_concurrent_run(self):
        logs_directory = Path(mkdtemp())
        executor = FlowExecutor.create(get_yaml_file(FLOW_FOLDER), {})
        flow_run_log_path = str(logs_directory / "test_flow_run.log")

        # flow run: test exec_line
        with LogContext(flow_run_log_path, run_mode=RunMode.Test):
            results = executor.exec_line(get_flow_inputs(FLOW_FOLDER))
            log_content = load_content(flow_run_log_path)
            pattern = r"\[wait_(\d+) in line None.*Thread (\d+)"
            matches = re.findall(pattern, log_content)
            wait_thread_mapping = {}
            for wait, thread in matches:
                if wait in wait_thread_mapping:
                    if wait_thread_mapping[wait] != thread:
                        raise Exception(f"wait_{wait} corresponds to more than one thread number")
                else:
                    wait_thread_mapping[wait] = thread
        self.assert_run_result(results)
        assert (
            results.run_info.system_metrics["duration"] < 10
        ), "run nodes concurrently should decrease the total run time."

    def test_concurrent_run_with_exception(self):
        executor = FlowExecutor.create(get_yaml_file(FLOW_FOLDER), {}, raise_ex=False)
        flow_result = executor.exec_line({"input1": "True", "input2": "False", "input3": "False", "input4": "False"})
        assert 2 < flow_result.run_info.system_metrics["duration"] < 4, "Should at least finish the running job."
        error_response = ErrorResponse.from_error_dict(flow_result.run_info.error)
        assert error_response.error_code_hierarchy == "UserError/ToolExecutionError"

    def test_linear_run(self):
        executor = FlowExecutor.create(get_yaml_file(FLOW_FOLDER), {})
        # flow run: test exec_line run linearly
        results = executor.exec_line(get_flow_inputs(FLOW_FOLDER), node_concurrency=RUN_FLOW_NODES_LINEARLY)
        self.assert_run_result(results)
        assert 15 > results.run_info.system_metrics["duration"] > 10, "run nodes linearly will consume more time."

    def assert_run_result(self, result: LineResult):
        # Validate the flow status
        assert result.run_info.status == Status.Completed
        # Validate the flow output
        assert isinstance(result.output, dict)
        # Validate the flow node run infos
        assert len(result.node_run_infos) == 5
