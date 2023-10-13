from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.logger_utils import LogContext
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor

from ..utils import get_yaml_file, load_content

TEST_LOGS_FLOW = ["print_input_flow"]


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorLogs:
    def assert_node_run_info(self, node_run_info, content):
        assert node_run_info.status == Status.Completed
        assert content in node_run_info.logs["stdout"]
        assert "STDOUT:" in node_run_info.logs["stdout"]
        assert content in node_run_info.logs["stderr"]
        assert "STDERR:" in node_run_info.logs["stderr"]

    def assert_flow_result(self, flow_result, content):
        assert isinstance(flow_result.output, dict)
        assert flow_result.run_info.status == Status.Completed
        for node_run_info in flow_result.node_run_infos.values():
            self.assert_node_run_info(node_run_info, content)

    @pytest.mark.parametrize(
        "folder_name",
        TEST_LOGS_FLOW,
    )
    def test_node_logs(self, folder_name):
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})
        content = "line_text"
        flow_result = executor.exec_line({"text": content})
        node_run_ids = [node_run_info.run_id for node_run_info in flow_result.node_run_infos.values()]
        for node_run_id in node_run_ids:
            logs = executor._run_tracker.node_log_manager.get_logs(node_run_id)
            assert logs["stderr"] is None and logs["stdout"] is None, f"Logs for node {node_run_id} is cleared."

        self.assert_flow_result(flow_result, content)

        bulk_inputs = [{"text": f"text_{idx}"} for idx in range(10)]
        bulk_results = executor.exec_bulk(bulk_inputs)
        for line_result in bulk_results.line_results:
            self.assert_flow_result(line_result, line_result.run_info.inputs["text"])

        content = "single_node_text"
        node_run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(folder_name),
            "print_input",
            flow_inputs={"text": content},
        )
        self.assert_node_run_info(node_run_info, content)

    @pytest.mark.parametrize(
        "folder_name",
        TEST_LOGS_FLOW,
    )
    def test_executor_logs(self, folder_name):
        logs_directory = Path(mkdtemp())
        flow_run_log_path = str(logs_directory / "test_flow_run.log")
        bulk_run_log_path = str(logs_directory / "test_bulk_run.log")

        # flow run: test exec_line
        with LogContext(flow_run_log_path):
            executor = FlowExecutor.create(get_yaml_file(folder_name), {})
            executor.exec_line({"text": "line_text"})
            log_content = load_content(flow_run_log_path)
            loggers_name_list = ["execution", "execution.flow"]
            assert all(logger in log_content for logger in loggers_name_list)

        # bulk run: test exec_bulk
        # setting run_mode to BulkTest is a requirement to use bulk_logger
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch):
            bulk_inputs = [{"text": f"text_{idx}"} for idx in range(10)]
            executor.exec_bulk(bulk_inputs)
            log_content = load_content(bulk_run_log_path)
            loggers_name_list = ["execution", "execution.bulk"]
            # bulk logger will print the average execution time and estimated time
            bulk_logs_keywords = ["Average execution time for completed lines", "Estimated time for incomplete lines"]
            assert all(logger in log_content for logger in loggers_name_list)
            assert all(keyword in log_content for keyword in bulk_logs_keywords)

    @pytest.mark.parametrize(
        "folder_name",
        TEST_LOGS_FLOW,
    )
    def test_node_logs_in_executor_logs(self, folder_name):
        logs_directory = Path(mkdtemp())
        flow_run_log_path = str(logs_directory / "test_flow_run.log")
        bulk_run_log_path = str(logs_directory / "test_bulk_run.log")

        # flow run: test exec_line
        with LogContext(flow_run_log_path, run_mode=RunMode.Test):
            executor = FlowExecutor.create(get_yaml_file(folder_name), {})
            executor.exec_line({"text": "line_text"})
            log_content = load_content(flow_run_log_path)
            node_logs_list = ["print_input in line", "stdout> STDOUT:", "stderr> STDERR:"]
            assert all(node_log in log_content for node_log in node_logs_list)

        # bulk run: test exec_bulk
        # setting run_mode to BulkTest is a requirement to use bulk_logger
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch):
            bulk_inputs = [{"text": f"text_{idx}"} for idx in range(10)]
            executor.exec_bulk(bulk_inputs)
            log_content = load_content(bulk_run_log_path)
            node_logs_list = ["print_input in line", "stderr> STDERR:"]
            assert all(node_log in log_content for node_log in node_logs_list)

    def test_long_run_log(self):
        executor = FlowExecutor.create(get_yaml_file("long_run"), {})
        file_path = Path(mkdtemp()) / "flow.log"
        with LogContext(file_path):
            flow_result = executor.exec_line({}, index=0)
        node_run = flow_result.node_run_infos["long_run_node"]
        assert node_run.status == Status.Completed
        with open(file_path) as fin:
            lines = fin.readlines()
        lines = [line for line in lines if line.strip()]
        target_texts = [
            "INFO     Start to run 1 nodes with concurrency level 16.",
            "INFO     Executing node long_run_node.",
            "WARNING  long_run_node in line 0 has been running for 60 seconds, stacktrace of thread",
            ", line 16, in long_run_func",
            "return f2()",
            ", line 11, in f2",
            "return f1()",
            ", line 6, in f1",
            "time.sleep(61)",
            "INFO     Node long_run_node completes.",
        ]
        msg = f"Got {len(lines)} lines in {file_path}, expected {len(target_texts)}."
        assert len(lines) == len(target_texts), msg
        for actual, expected in zip(lines, target_texts):
            assert expected in actual, f"Expected {expected} in {actual}"
