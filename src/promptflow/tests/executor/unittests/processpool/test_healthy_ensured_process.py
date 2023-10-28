import pytest

from multiprocessing import Queue
from promptflow.executor._line_execution_process_pool import HealthyEnsuredProcess

from unittest.mock import patch
import time


def executor_creation_func(storage):
    pass


def executor_creation_func_timeout(storage):
    time.sleep(60)
    pass


def end_process(healthy_ensured_process):
    while healthy_ensured_process.process.is_alive():
        healthy_ensured_process.end()
        time.sleep(1)
    return


@pytest.mark.unittest
class TestHealthyEnsuredProcess:

    def test_healthy_ensured_process(self):
        healthy_ensured_process = HealthyEnsuredProcess(executor_creation_func)
        assert healthy_ensured_process.is_ready is False
        task_queue = Queue()
        healthy_ensured_process.start_new(task_queue)
        assert healthy_ensured_process.process.is_alive()
        assert healthy_ensured_process.is_ready is True
        end_process(healthy_ensured_process)
        assert healthy_ensured_process.process.is_alive() is False

    def test_unhealthy_process(self):
        healthy_ensured_process = HealthyEnsuredProcess(executor_creation_func_timeout)
        assert healthy_ensured_process.is_ready is False
        task_queue = Queue()
        healthy_ensured_process.start_new(task_queue)
        assert healthy_ensured_process.process.is_alive() is True
        assert healthy_ensured_process.is_ready is False
        end_process(healthy_ensured_process)
        assert healthy_ensured_process.process.is_alive() is False

    def test_format_current_process(self):
        healthy_ensured_process = HealthyEnsuredProcess(executor_creation_func)
        healthy_ensured_process.process = patch(
            'promptflow.executor._line_execution_process_pool.Process', autospec=True)
        healthy_ensured_process.process.name = "process_name"
        healthy_ensured_process.process.pid = 123
        line_number = 13
        formatted_message = healthy_ensured_process.format_current_process(line_number)
        process_name = healthy_ensured_process.process.name
        process_pid = healthy_ensured_process.process.pid
        expected_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number})"
        )
        assert formatted_message == expected_log_message

    @patch('promptflow.executor._line_execution_process_pool.logger.info', autospec=True)
    def test_format_completed_process(self, mock_logger_info):
        healthy_ensured_process = HealthyEnsuredProcess(executor_creation_func)
        healthy_ensured_process.process = patch(
            'promptflow.executor._line_execution_process_pool.Process', autospec=True)
        healthy_ensured_process.process.name = "process_name"
        healthy_ensured_process.process.pid = 123
        line_number = 13
        mock_logger_info.reset_mock()
        healthy_ensured_process.format_current_process(line_number, True)
        process_name = healthy_ensured_process.process.name
        process_pid = healthy_ensured_process.process.pid
        exexpected_log_message = (
            f"Process name: {process_name}, Process id: {process_pid}, Line number: {line_number} completed."
        )
        mock_logger_info.assert_called_once_with(exexpected_log_message)
