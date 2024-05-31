import os
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._constants import LINE_NUMBER_WIDTH, OUTPUT_FILE_NAME
from promptflow._utils.logger_utils import LogContext
from promptflow.batch import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor

from ..utils import (
    EAGER_FLOW_ROOT,
    FLOW_ROOT,
    count_lines,
    get_batch_inputs_line,
    get_bulk_inputs_from_jsonl,
    get_flow_folder,
    get_flow_inputs_file,
    get_yaml_file,
    load_content,
    load_jsonl,
    submit_batch_run,
)

TEST_LOGS_FLOW = ["print_input_flow"]
SAMPLE_FLOW_WITH_TEN_INPUTS = "simple_flow_with_ten_inputs"


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

    def submit_bulk_run(self, folder_name, root=FLOW_ROOT):
        batch_engine = BatchEngine(
            get_yaml_file(folder_name, root=root), get_flow_folder(folder_name, root=root), connections={}
        )
        input_dirs = {"data": get_flow_inputs_file(folder_name, root=root)}
        inputs_mapping = {"text": "${data.text}"}
        output_dir = Path(mkdtemp())
        return batch_engine.run(input_dirs, inputs_mapping, output_dir)

    @pytest.mark.parametrize(
        "folder_name",
        TEST_LOGS_FLOW,
    )
    def test_node_logs(self, folder_name):
        # Test node logs in flow run
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})
        content = "line_text"
        flow_result = executor.exec_line({"text": content})
        node_run_ids = [node_run_info.run_id for node_run_info in flow_result.node_run_infos.values()]
        for node_run_id in node_run_ids:
            logs = executor._run_tracker.node_log_manager.get_logs(node_run_id)
            assert logs["stderr"] is None and logs["stdout"] is None, f"Logs for node {node_run_id} is cleared."
        self.assert_flow_result(flow_result, content)

        # Test node logs in single node run
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
            missing_loggers = [logger for logger in loggers_name_list if logger not in log_content]
            assert not missing_loggers, f"Missing loggers: {missing_loggers}\nLog content:\n---\n{log_content}"
            line_count = count_lines(flow_run_log_path)
            assert 6 == line_count, f"Expected 6 lines in log, but got {line_count}\nLog content:\n---\n{log_content}"

        # bulk run: test batch_engine.run
        # setting run_mode to BulkTest is a requirement to use bulk_logger
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch):
            self.submit_bulk_run(folder_name)
            log_content = load_content(bulk_run_log_path)
            loggers_name_list = ["execution", "execution.bulk"]
            # bulk logger will print the average execution time and estimated time
            bulk_logs_keywords = ["Average execution time for completed lines", "Estimated time for incomplete lines"]
            assert all(logger in log_content for logger in loggers_name_list)
            assert all(keyword in log_content for keyword in bulk_logs_keywords)
            # Customer facing log is really important, so we pay the effort to make change
            # about test wehen line count change a lot in the future.
            line_count = count_lines(bulk_run_log_path)
            assert 40 <= line_count <= 50

        import shutil

        shutil.rmtree(logs_directory)

    @pytest.mark.parametrize(
        "flow_root_dir, flow_folder_name, line_number",
        [[FLOW_ROOT, "print_input_flow", 8], [EAGER_FLOW_ROOT, "print_input_flex", 2]],
    )
    def test_batch_run_flow_logs(self, flow_root_dir, flow_folder_name, line_number):
        logs_directory = Path(mkdtemp())
        bulk_run_log_path = str(logs_directory / "test_bulk_run.log")
        bulk_run_flow_logs_folder = str(logs_directory / "test_bulk_run_flow_logs_folder")
        Path(bulk_run_flow_logs_folder).mkdir()
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch, flow_logs_folder=bulk_run_flow_logs_folder):
            self.submit_bulk_run(flow_folder_name, root=flow_root_dir)
            nlines = len(get_bulk_inputs_from_jsonl(flow_folder_name, root=flow_root_dir))
            for i in range(nlines):
                file_name = f"{str(i).zfill(LINE_NUMBER_WIDTH)}.log"
                flow_log_file = Path(bulk_run_flow_logs_folder) / file_name
                assert flow_log_file.is_file()
                log_content = load_content(flow_log_file)
                # Assert flow log file contains expected logs
                assert "execution          WARNING" in log_content
                assert "execution.flow     INFO" in log_content
                assert f"in line {i} (index starts from 0)" in log_content
                # Some monitor logs may not be printed in CI test.
                # Assert max line number to avoid printing too many noisy logs.
                assert line_number == count_lines(
                    flow_log_file
                ), f"log line count is incorrect, content is {log_content}"

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

        # bulk run: test batch_engine.run
        # setting run_mode to BulkTest is a requirement to use bulk_logger
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch):
            self.submit_bulk_run(folder_name)
            log_content = load_content(bulk_run_log_path)
            node_logs_list = ["print_input in line", "stderr> STDERR:"]
            assert all(node_log in log_content for node_log in node_logs_list)

    def test_long_run_log(self):
        # Test long running tasks with log
        os.environ["PF_LONG_RUNNING_LOGGING_INTERVAL"] = "60"
        target_texts = [
            "INFO     Start executing nodes in thread pool mode.",
            "INFO     Start to run 1 nodes with concurrency level 16.",
            "INFO     Executing node long_run_node.",
            "INFO     Using value of PF_LONG_RUNNING_LOGGING_INTERVAL in environment variable",
            "WARNING  long_run_node in line 0 has been running for 60 seconds, stacktrace of thread",
            "in wrapped",
            "output = func(*args, **kwargs)",
            ", line 16, in long_run_func",
            "return f2()",
            ", line 11, in f2",
            "return f1()",
            ", line 6, in f1",
            "time.sleep(61)",
            "INFO     Node long_run_node completes.",
        ]
        self.assert_long_run_log(target_texts)
        os.environ.pop("PF_LONG_RUNNING_LOGGING_INTERVAL")

        # Test long running tasks without log
        target_texts = [
            "INFO     Start executing nodes in thread pool mode.",
            "INFO     Start to run 1 nodes with concurrency level 16.",
            "INFO     Executing node long_run_node.",
            "INFO     Node long_run_node completes.",
        ]
        self.assert_long_run_log(target_texts)

    def assert_long_run_log(self, target_texts):
        executor = FlowExecutor.create(get_yaml_file("long_run"), {})
        file_path = Path(mkdtemp()) / "flow.log"
        with LogContext(file_path):
            flow_result = executor.exec_line({}, index=0)
        node_run = flow_result.node_run_infos["long_run_node"]
        assert node_run.status == Status.Completed
        with open(file_path) as fin:
            lines = fin.readlines()
        lines = [line for line in lines if line.strip()]
        msg = f"Got {len(lines)} lines in {file_path}, expected {len(target_texts)}."
        assert len(lines) == len(target_texts), msg
        for actual, expected in zip(lines, target_texts):
            assert expected in actual, f"Expected {expected} in {actual}"

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            (
                SAMPLE_FLOW_WITH_TEN_INPUTS,
                {"input": "${data.input}", "index": "${data.index}"},
            )
        ],
    )
    def test_log_progress(self, flow_folder, inputs_mapping, dev_connections):
        logs_directory = Path(mkdtemp())
        bulk_run_log_path = str(logs_directory / "test_bulk_run.log")
        with LogContext(bulk_run_log_path, run_mode=RunMode.Batch):
            batch_result, output_dir = submit_batch_run(
                flow_folder, inputs_mapping, connections=dev_connections, return_output_dir=True
            )
            nlines = get_batch_inputs_line(flow_folder)
            log_content = load_content(bulk_run_log_path)
            for i in range(1, nlines + 1):
                assert f"Finished {i} / {nlines} lines." in log_content
            assert isinstance(batch_result, BatchResult)
            assert batch_result.total_lines == nlines
            assert batch_result.completed_lines == nlines
            assert batch_result.start_time < batch_result.end_time
            assert batch_result.system_metrics.duration > 0

            outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
            assert len(outputs) == nlines
            for i, output in enumerate(outputs):
                assert isinstance(output, dict)
                assert "line_number" in output, f"line_number is not in {i}th output {output}"
                assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"

    def test_activate_config_log(self):
        logs_directory = Path(mkdtemp())
        log_path = str(logs_directory / "flow.log")

        # flow run: test exec_line
        with LogContext(log_path, run_mode=RunMode.Test):
            executor = FlowExecutor.create(get_yaml_file("activate_flow"), {})
            # use default inputs
            executor.exec_line({})
            log_content = load_content(log_path)
            logs_list = [
                "execution.flow",
                "The node 'nodeA' will be bypassed because the activate condition is not met, "
                "i.e. '${flow.text}' is not equal to 'hello'.",
                "The node 'nodeB' will be bypassed because it depends on the node 'nodeA' "
                "which has already been bypassed in the activate config.",
                "The node 'nodeC' will be bypassed because all nodes ['nodeB'] it depends on are bypassed.",
                "The node 'nodeD' will be executed because the activate condition is met, "
                "i.e. '${flow.text}' is equal to 'world'.",
            ]
            assert all(log in log_content for log in logs_list)

    def test_async_log_in_worker_thread(self):
        os.environ["PF_LONG_RUNNING_LOGGING_INTERVAL"] = "60"
        logs_directory = Path(mkdtemp())
        log_path = str(logs_directory / "flow.log")
        with LogContext(log_path, run_mode=RunMode.Test):
            executor = FlowExecutor.create(get_yaml_file("async_tools"), {})
            executor.exec_line(inputs={})
            log_content = load_content(log_path)
            # Below log is created by worker thread
            logs_list = ["INFO     monitor_long_running_coroutine started"]
            assert all(log in log_content for log in logs_list)
        os.environ.pop("PF_LONG_RUNNING_LOGGING_INTERVAL")

    def test_change_log_format(self, monkeypatch):
        # Change log format
        date_format = "%Y/%m/%d %H:%M:%S"
        log_format = "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
        monkeypatch.setenv("PF_LOG_FORMAT", log_format)
        monkeypatch.setenv("PF_LOG_DATETIME_FORMAT", date_format)

        logs_directory = Path(mkdtemp())
        log_path = str(logs_directory / "flow.log")
        with LogContext(log_path):
            executor = FlowExecutor.create(get_yaml_file("print_input_flow"), {})
            executor.exec_line(inputs={"text": "line_text"})
            log_content = load_content(log_path)
            current_date = datetime.now().strftime("%Y/%m/%d")
            logs_list = [
                f"[{current_date}",
                "[execution.flow][INFO] - Start executing nodes in thread pool mode.",
                "[execution.flow][INFO] - Executing node print_input.",
                "[execution.flow][INFO] - Node print_input completes.",
                "stderr> STDERR: line_text",
            ]
            assert all(
                log in log_content for log in logs_list
            ), f"Missing logs are [{[log for log in logs_list if log not in log_content]}]"
