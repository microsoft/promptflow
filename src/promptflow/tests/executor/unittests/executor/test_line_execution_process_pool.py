import multiprocessing
import os
import sys
import uuid
from multiprocessing import Queue
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
from pytest_mock import MockFixture

from promptflow._utils.logger_utils import LogContext
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import SpawnedForkProcessManagerStartFailure
from promptflow.executor._line_execution_process_pool import (
    LineExecutionProcessPool,
    _exec_line,
    format_current_process_info,
    log_process_status,
)
from promptflow.executor._process_manager import ProcessPoolConstants, create_spawned_fork_process_manager
from promptflow.executor._result import LineResult

from ...utils import get_flow_sample_inputs, get_yaml_file

SAMPLE_FLOW = "hello-world"


def get_line_inputs(flow_folder=""):
    if flow_folder:
        inputs = get_bulk_inputs(flow_folder)
        return inputs[0]
    return {
        "url": "https://www.microsoft.com/en-us/windows/",
        "text": "some_text",
    }


def get_bulk_inputs(nlinee=4, flow_folder="", sample_inputs_file="", return_dict=False):
    if flow_folder:
        if not sample_inputs_file:
            sample_inputs_file = "samples.json"
        inputs = get_flow_sample_inputs(flow_folder, sample_inputs_file=sample_inputs_file)
        if isinstance(inputs, list) and len(inputs) > 0:
            return inputs
        elif isinstance(inputs, dict):
            if return_dict:
                return inputs
            return [inputs]
        else:
            raise Exception(f"Invalid type of bulk input: {inputs}")
    return [get_line_inputs() for _ in range(nlinee)]


def execute_in_fork_mode_subprocess(dev_connections, flow_folder, has_passed_worker_count, pf_worker_count, n_process):
    os.environ["PF_BATCH_METHOD"] = "fork"
    executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
    run_id = str(uuid.uuid4())
    bulk_inputs = get_bulk_inputs()
    nlines = len(bulk_inputs)

    with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
        with LineExecutionProcessPool(
            None,
            executor,
            nlines=nlines,
            run_id=run_id,
            worker_count=pf_worker_count if has_passed_worker_count else None,
        ) as pool:
            assert pool._n_process == n_process
            if has_passed_worker_count:
                mock_logger.info.assert_any_call(f"Set process count to {pf_worker_count}.")
            else:
                factors = {
                    "default_worker_count": pool._DEFAULT_WORKER_COUNT,
                    "row_count": pool._nlines,
                }
                mock_logger.info.assert_any_call(
                    f"Set process count to {n_process} by taking the minimum value among the " f"factors of {factors}."
                )


def execute_in_spawn_mode_subprocess(
    dev_connections,
    flow_folder,
    has_passed_worker_count,
    is_calculation_smaller_than_set,
    pf_worker_count,
    estimated_available_worker_count,
    n_process,
):
    os.environ["PF_BATCH_METHOD"] = "spawn"
    executor = FlowExecutor.create(
        get_yaml_file(flow_folder),
        dev_connections,
    )
    run_id = str(uuid.uuid4())
    bulk_inputs = get_bulk_inputs()
    nlines = len(bulk_inputs)

    with patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value.available = 128.0 * 1024 * 1024
        with patch("psutil.Process") as mock_process:
            mock_process.return_value.memory_info.return_value.rss = 64 * 1024 * 1024
            with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
                with LineExecutionProcessPool(
                    None,
                    executor,
                    nlines=nlines,
                    run_id=run_id,
                    worker_count=pf_worker_count if has_passed_worker_count else None,
                ) as pool:
                    assert pool._n_process == n_process
                    if has_passed_worker_count and is_calculation_smaller_than_set:
                        mock_logger.info.assert_any_call(f"Set process count to {pf_worker_count}.")
                        mock_logger.warning.assert_any_call(
                            f"The current process count ({pf_worker_count}) is larger than recommended process count "
                            f"({estimated_available_worker_count}) that estimated by system available memory. This may "
                            f"cause memory exhaustion"
                        )
                    elif has_passed_worker_count and not is_calculation_smaller_than_set:
                        mock_logger.info.assert_any_call(f"Set process count to {pf_worker_count}.")
                    elif not has_passed_worker_count:
                        factors = {
                            "default_worker_count": pool._DEFAULT_WORKER_COUNT,
                            "row_count": pool._nlines,
                            "estimated_worker_count_based_on_memory_usage": estimated_available_worker_count,
                        }
                        mock_logger.info.assert_any_call(
                            f"Set process count to {n_process} by taking the minimum value among the factors "
                            f"of {factors}."
                        )


def create_line_execution_process_pool(dev_connections):
    executor = FlowExecutor.create(get_yaml_file(SAMPLE_FLOW), dev_connections)
    run_id = str(uuid.uuid4())
    bulk_inputs = get_bulk_inputs()
    nlines = len(bulk_inputs)
    line_execution_process_pool = LineExecutionProcessPool(
        None,
        executor,
        nlines=nlines,
        run_id=run_id,
        line_timeout_sec=1,
    )
    return line_execution_process_pool


def set_environment_successed_in_subprocess(dev_connections, pf_batch_method):
    os.environ["PF_BATCH_METHOD"] = pf_batch_method
    line_execution_process_pool = create_line_execution_process_pool(dev_connections)
    use_fork = line_execution_process_pool._use_fork
    assert use_fork is False


def set_environment_failed_in_subprocess(dev_connections):
    with patch("promptflow.executor._line_execution_process_pool.bulk_logger") as mock_logger:
        mock_logger.warning.return_value = None
        os.environ["PF_BATCH_METHOD"] = "test"
        line_execution_process_pool = create_line_execution_process_pool(dev_connections)
        use_fork = line_execution_process_pool._use_fork
        assert use_fork == (multiprocessing.get_start_method() == "fork")
        sys_start_methods = multiprocessing.get_all_start_methods()
        exexpected_log_message = (
            "Failed to set start method to 'test', start method test" f" is not in: {sys_start_methods}."
        )
        mock_logger.warning.assert_called_once_with(exexpected_log_message)


def not_set_environment_in_subprocess(dev_connections):
    line_execution_process_pool = create_line_execution_process_pool(dev_connections)
    use_fork = line_execution_process_pool._use_fork
    assert use_fork == (multiprocessing.get_start_method() == "fork")


def custom_create_spawned_fork_process_manager(*args, **kwargs):
    create_spawned_fork_process_manager("test", *args, **kwargs)


@pytest.mark.unittest
@pytest.mark.usefixtures("recording_injection")
class TestLineExecutionProcessPool:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    async def test_line_execution_process_pool(self, flow_folder, dev_connections):
        log_path = str(Path(mkdtemp()) / "test.log")
        log_context_initializer = LogContext(log_path).get_initializer()
        log_context = log_context_initializer()
        with log_context:
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
            executor._log_interval = 1
            run_id = str(uuid.uuid4())
            bulk_inputs = get_bulk_inputs()
            nlines = len(bulk_inputs)
            run_id = run_id or str(uuid.uuid4())
            with LineExecutionProcessPool(
                None,
                executor,
                nlines=nlines,
                run_id=run_id,
            ) as pool:
                result_list = await pool.run(zip(range(nlines), bulk_inputs))
                if sys.platform == "linux":
                    # Check 'spawned_fork_process_manager_stderr_runid.log' exits.
                    log_file = ProcessPoolConstants.PROCESS_LOG_PATH / ProcessPoolConstants.MANAGER_PROCESS_LOG_NAME
                    assert log_file.exists() is True
                child_process_log_exit = False
                for file in ProcessPoolConstants.PROCESS_LOG_PATH.iterdir():
                    # Check 'process_stderr.log' exits.
                    if file.name.startswith(ProcessPoolConstants.PROCESS_LOG_NAME):
                        child_process_log_exit = True
                assert child_process_log_exit is True
            assert len(result_list) == nlines
            for i, line_result in enumerate(result_list):
                assert isinstance(line_result, LineResult)
                assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    async def test_line_execution_not_completed(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        run_id = str(uuid.uuid4())
        bulk_inputs = get_bulk_inputs()
        nlines = len(bulk_inputs)
        with LineExecutionProcessPool(
            None,
            executor,
            nlines=nlines,
            run_id=run_id,
            line_timeout_sec=1,
        ) as pool:
            result_list = await pool.run(zip(range(nlines), bulk_inputs))
        assert len(result_list) == nlines
        for i, line_result in enumerate(result_list):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.error["message"] == f"Line {i} execution timeout for exceeding 1 seconds"
            assert line_result.run_info.error["code"] == "UserError"
            assert line_result.run_info.status == Status.Failed

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_exec_line(self, flow_folder, dev_connections, mocker: MockFixture):
        output_queue = Queue()
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        run_id = str(uuid.uuid4())
        line_inputs = get_line_inputs()
        line_result = _exec_line(
            executor=executor,
            output_queue=output_queue,
            inputs=line_inputs,
            run_id=run_id,
            index=0,
            line_timeout_sec=600,
        )
        assert isinstance(line_result, LineResult)

    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    def test_exec_line_failed_when_line_execution_not_start(self, flow_folder, dev_connections, mocker: MockFixture):
        output_queue = Queue()
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        test_error_msg = "Test user error"
        with patch("promptflow.executor.flow_executor.FlowExecutor.exec_line", autouse=True) as mock_exec_line:
            mock_exec_line.side_effect = UserErrorException(
                message=test_error_msg, target=ErrorTarget.AZURE_RUN_STORAGE
            )
            run_id = str(uuid.uuid4())
            line_inputs = get_line_inputs()
            line_result = _exec_line(
                executor=executor,
                output_queue=output_queue,
                inputs=line_inputs,
                run_id=run_id,
                index=0,
                line_timeout_sec=600,
            )
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.error["message"] == test_error_msg
            assert line_result.run_info.error["code"] == "UserError"
            assert line_result.run_info.status == Status.Failed

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    async def test_process_pool_run_with_exception(self, flow_folder, dev_connections, mocker: MockFixture):
        # mock process pool run execution raise error
        test_error_msg = "Test user error"
        mocker.patch(
            "promptflow.executor._line_execution_process_pool.LineExecutionProcessPool."
            "_monitor_workers_and_process_tasks_in_thread",
            side_effect=UserErrorException(message=test_error_msg, target=ErrorTarget.AZURE_RUN_STORAGE),
        )
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        run_id = str(uuid.uuid4())
        bulk_inputs = get_bulk_inputs()
        nlines = len(bulk_inputs)
        with LineExecutionProcessPool(
            None,
            executor,
            nlines=nlines,
            run_id=run_id,
        ) as pool:
            with pytest.raises(UserErrorException) as e:
                await pool.run(zip(range(nlines), bulk_inputs))
            assert e.value.message == test_error_msg
            assert e.value.target == ErrorTarget.AZURE_RUN_STORAGE
            assert e.value.error_codes[0] == "UserError"

    @pytest.mark.parametrize(
        ("flow_folder", "has_passed_worker_count", "pf_worker_count", "n_process"),
        [(SAMPLE_FLOW, True, 3, 3), (SAMPLE_FLOW, False, None, 4)],
    )
    def test_process_pool_parallelism_in_fork_mode(
        self, dev_connections, flow_folder, has_passed_worker_count, pf_worker_count, n_process
    ):
        if "fork" not in multiprocessing.get_all_start_methods():
            pytest.skip("Unsupported start method: fork")
        p = multiprocessing.Process(
            target=execute_in_fork_mode_subprocess,
            args=(dev_connections, flow_folder, has_passed_worker_count, pf_worker_count, n_process),
        )
        p.start()
        p.join()
        assert p.exitcode == 0

    @pytest.mark.parametrize(
        (
            "flow_folder",
            "has_passed_worker_count",
            "is_calculation_smaller_than_set",
            "pf_worker_count",
            "estimated_available_worker_count",
            "n_process",
        ),
        [
            (SAMPLE_FLOW, True, False, 2, 4, 2),
            (SAMPLE_FLOW, True, True, 6, 2, 6),
            (SAMPLE_FLOW, False, True, None, 2, 2),
        ],
    )
    def test_process_pool_parallelism_in_spawn_mode(
        self,
        dev_connections,
        flow_folder,
        has_passed_worker_count,
        is_calculation_smaller_than_set,
        pf_worker_count,
        estimated_available_worker_count,
        n_process,
    ):
        if "spawn" not in multiprocessing.get_all_start_methods():
            pytest.skip("Unsupported start method: spawn")
        p = multiprocessing.Process(
            target=execute_in_spawn_mode_subprocess,
            args=(
                dev_connections,
                flow_folder,
                has_passed_worker_count,
                is_calculation_smaller_than_set,
                pf_worker_count,
                estimated_available_worker_count,
                n_process,
            ),
        )
        p.start()
        p.join()
        assert p.exitcode == 0

    def test_process_set_environment_variable_successed(self, dev_connections):
        p = multiprocessing.Process(
            target=set_environment_successed_in_subprocess,
            args=(
                dev_connections,
                "spawn",
            ),
        )
        p.start()
        p.join()
        assert p.exitcode == 0

    def test_process_set_environment_variable_failed(self, dev_connections):
        p = multiprocessing.Process(target=set_environment_failed_in_subprocess, args=(dev_connections,))
        p.start()
        p.join()
        assert p.exitcode == 0

    def test_process_not_set_environment_variable(self, dev_connections):
        p = multiprocessing.Process(target=not_set_environment_in_subprocess, args=(dev_connections,))
        p.start()
        p.join()
        assert p.exitcode == 0

    @pytest.mark.skipif(sys.platform == "win32" or sys.platform == "darwin", reason="Only test on linux")
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flow_folder",
        [
            SAMPLE_FLOW,
        ],
    )
    @patch(
        "promptflow.executor._process_manager.create_spawned_fork_process_manager",
        custom_create_spawned_fork_process_manager,
    )
    async def test_spawned_fork_process_manager_crashed_in_fork_mode(self, flow_folder, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        run_id = str(uuid.uuid4())
        bulk_inputs = get_bulk_inputs()
        nlines = len(bulk_inputs)
        run_id = run_id or str(uuid.uuid4())
        with pytest.raises(SpawnedForkProcessManagerStartFailure) as e:
            with LineExecutionProcessPool(
                None,
                executor,
                nlines=nlines,
                run_id=run_id,
            ) as pool:
                await pool.run(zip(range(nlines), bulk_inputs))
        assert "Failed to start spawned fork process manager" in str(e.value)


@pytest.mark.unittest
class TestFormatCurrentProcess:
    def test_format_current_process_info(self):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        formatted_message = format_current_process_info(process_name, process_pid, line_number)
        expected_returned_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number})"
        )
        assert formatted_message == expected_returned_log_message

    @patch("promptflow.executor._line_execution_process_pool.bulk_logger.info", autospec=True)
    def test_log_process_status_start_execution(self, mock_logger_info):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        log_process_status(process_name, process_pid, line_number)
        exexpected_during_execution_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number}) start execution."
        )
        mock_logger_info.assert_called_once_with(exexpected_during_execution_log_message)

    @patch("promptflow.executor._line_execution_process_pool.bulk_logger.info", autospec=True)
    def test_log_process_status_completed(self, mock_logger_info):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        log_process_status(process_name, process_pid, line_number, is_completed=True)
        exexpected_during_execution_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number}) completed."
        )
        mock_logger_info.assert_called_once_with(exexpected_during_execution_log_message)

    @patch("promptflow.executor._line_execution_process_pool.bulk_logger.info", autospec=True)
    def test_log_process_status_failed(self, mock_logger_info):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        log_process_status(process_name, process_pid, line_number, is_failed=True)
        exexpected_during_execution_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number}) failed."
        )
        mock_logger_info.assert_called_once_with(exexpected_during_execution_log_message)
