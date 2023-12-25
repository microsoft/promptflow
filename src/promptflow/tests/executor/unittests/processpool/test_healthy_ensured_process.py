import pytest

from promptflow.executor._line_execution_process_pool import format_current_process

from unittest.mock import patch


@pytest.mark.unittest
class TestHealthyEnsuredProcess:
    @patch('promptflow.executor._line_execution_process_pool.bulk_logger.info', autospec=True)
    def test_format_current_process(self, mock_logger_info):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        formatted_message = format_current_process(process_name, process_pid, line_number)
        exexpected_during_execution_log_message = (
            f"Process name: {process_name}, Process id: {process_pid}, Line number: {line_number} start execution."
        )
        expected_returned_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number})"
        )
        mock_logger_info.assert_called_once_with(exexpected_during_execution_log_message)
        assert formatted_message == expected_returned_log_message

    @patch('promptflow.executor._line_execution_process_pool.bulk_logger.info', autospec=True)
    def test_format_completed_process(self, mock_logger_info):
        process_name = "process_name"
        process_pid = 123
        line_number = 13
        formatted_message = format_current_process(process_name, process_pid, line_number, True)
        exexpected_during_execution_log_message = (
            f"Process name: {process_name}, Process id: {process_pid}, Line number: {line_number} completed."
        )
        expected_returned_log_message = (
            f"Process name({process_name})-Process id({process_pid})-Line number({line_number})"
        )
        mock_logger_info.assert_called_once_with(exexpected_during_execution_log_message)
        assert formatted_message == expected_returned_log_message
