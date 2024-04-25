import json
import os
import sys
import time
from unittest.mock import patch

import pytest

from promptflow._core._errors import UnexpectedError
from promptflow._utils.exception_utils import JsonSerializedPromptflowException
from promptflow.exceptions import ErrorTarget
from promptflow.executor._service._errors import ExecutionTimeoutError
from promptflow.executor._service.utils.process_utils import (
    _execute_target_function,
    exception_wrapper,
    invoke_sync_function_in_process,
)
from promptflow.tracing._operation_context import OperationContext

MOCK_CONTEXT_DICT = {"context_test_key": "test_value"}


def target_function(request: int):
    operation_context = OperationContext.get_instance()
    assert operation_context.context_test_key == "test_value"
    if request == 0:
        # raise exception to simulate error during executing the target function
        raise Exception("Test exception")
    elif request < 0:
        # exit current process with exit code -1 to simulate unexpected error
        sys.exit(1)
    # sleep for the request seconds to simulate the timeout case
    time.sleep(request)
    return request


def target_function_get_env(environment_variable: str):
    return os.getenv(environment_variable)


@pytest.mark.unittest
class TestProcessUtils:
    @pytest.mark.asyncio
    async def test_invoke_sync_function_in_process_completed(self):
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            result = await invoke_sync_function_in_process(target_function, args=(1,), context_dict=MOCK_CONTEXT_DICT)
            assert result == 1
            assert mock_logger.info.call_count == 2
            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoke_sync_function_in_process_timeout(self):
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            with pytest.raises(ExecutionTimeoutError) as exc_info:
                await invoke_sync_function_in_process(
                    target_function, args=(10,), context_dict=MOCK_CONTEXT_DICT, wait_timeout=2
                )
            assert exc_info.value.message == "Execution timeout for exceeding 2 seconds"
            assert exc_info.value.target == ErrorTarget.EXECUTOR
            mock_logger.info.assert_called_once()
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_sync_function_in_process_exception(self):
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            with pytest.raises(JsonSerializedPromptflowException) as exc_info:
                await invoke_sync_function_in_process(target_function, args=(0,), context_dict=MOCK_CONTEXT_DICT)
            assert json.loads(exc_info.value.message)["message"] == "Test exception"
            mock_logger.info.assert_called_once()
            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoke_sync_function_in_process_unexpected_error(self):
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            with pytest.raises(UnexpectedError) as exc_info:
                await invoke_sync_function_in_process(target_function, args=(-1,), context_dict=MOCK_CONTEXT_DICT)
            assert exc_info.value.message == "Unexpected error occurred while executing the request"
            assert exc_info.value.target == ErrorTarget.EXECUTOR
            mock_logger.info.assert_called_once()
            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoke_sync_function_in_process_set_env(self):
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            environment_variables = {"test_env_name": "test_env_value"}
            result = await invoke_sync_function_in_process(
                target_function_get_env,
                args=("test_env_name",),
                context_dict=MOCK_CONTEXT_DICT,
                environment_variables=environment_variables,
            )
            assert result == "test_env_value"
            assert mock_logger.info.call_count == 2
            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_target_function_completed(self):
        return_dict = {}
        error_dict = {}
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            _execute_target_function(target_function, (1,), {}, return_dict, error_dict, MOCK_CONTEXT_DICT, None)
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_target_function_exception(self):
        return_dict = {}
        error_dict = {}
        with patch("promptflow.executor._service.utils.process_utils.service_logger") as mock_logger:
            with pytest.raises(JsonSerializedPromptflowException) as exc_info:
                _execute_target_function(target_function, (0,), {}, return_dict, error_dict, MOCK_CONTEXT_DICT, None)
            assert json.loads(exc_info.value.message)["message"] == "Test exception"
            mock_logger.info.assert_called_once()

    def test_exception_wrapper_without_exception(self):
        error_dict = {}
        with exception_wrapper(error_dict):
            pass
        assert error_dict.get("error", None) is None

    def test_exception_wrapper_with_exception(self):
        error_dict = {}
        error_message = "This is a test exception"

        with pytest.raises(JsonSerializedPromptflowException):
            with exception_wrapper(error_dict):
                raise ValueError(error_message)

        exception = error_dict.get("error")
        assert isinstance(exception, JsonSerializedPromptflowException)

        exception_detail = json.loads(exception.message)
        assert exception_detail["code"] == "SystemError"
        assert exception_detail["innerError"]["code"] == "ValueError"
        assert exception_detail["message"] == error_message
