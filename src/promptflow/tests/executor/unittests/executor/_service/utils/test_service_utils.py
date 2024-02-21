import json
import os
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException, ResponseCode
from promptflow._utils.logger_utils import bulk_logger, flow_logger, logger, service_logger
from promptflow.executor._service._errors import ExecutionTimeoutError
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest, FlowExecutionRequest
from promptflow.executor._service.utils.service_utils import (
    generate_error_response,
    get_executor_version,
    get_log_context,
    get_service_log_context,
    set_environment_variables,
    update_and_get_operation_context,
)

from .....utils import load_content
from ..contracts.test_execution_request import MOCK_REQUEST


@pytest.mark.unittest
class TestServiceUtils:
    def test_get_log_context(self, dev_connections):
        request = FlowExecutionRequest(**MOCK_REQUEST)
        request.connections = dev_connections
        request.log_path = Path(mkdtemp()) / "log.txt"
        with get_log_context(request):
            flow_logger.info("Test flow_logger log")
            bulk_logger.info("Test bulk_logger log")
            logger.info("Test logger log")
        logs = load_content(request.log_path)
        keywords_in_log = ["Test flow_logger log", "Test logger log", "execution", "execution.flow"]
        keywords_not_in_log = ["Test bulk_logger log", "execution.bulk"]
        assert all(word in logs for word in keywords_in_log)
        assert all(word not in logs for word in keywords_not_in_log)

    def test_get_service_log_context(self):
        request = FlowExecutionRequest(**MOCK_REQUEST)
        request.log_path = Path(mkdtemp()) / "log.txt"
        with get_service_log_context(request):
            service_logger.info("Test service_logger log")
            flow_logger.info("Test flow_logger log")
            bulk_logger.info("Test bulk_logger log")
            logger.info("Test logger log")
        logs = load_content(request.log_path)
        keywords_in_log = [
            "Test service_logger log",
            "Test flow_logger log",
            "Test logger log",
            "execution.service",
            "execution",
            "execution.flow",
        ]
        keywords_not_in_log = ["Test bulk_logger log", "execution.bulk"]
        assert all(word in logs for word in keywords_in_log)
        assert all(word not in logs for word in keywords_not_in_log)

    def test_update_and_get_operation_context(self, monkeypatch):
        context_dict = {
            "user_agent": "dummy_user_agent",
            "request_id": "dummy_request_id",
        }
        # mock the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"build_number": "20240131.v1"}')

        operation_context = update_and_get_operation_context(context_dict)
        assert operation_context.user_agent == "dummy_user_agent promptflow-executor/20240131.v1"
        assert operation_context.request_id == "dummy_request_id"

    def test_get_executor_version(self, monkeypatch):
        # mock have the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"build_number": "20240131.v1"}')
        executor_version = get_executor_version()
        assert executor_version == "promptflow-executor/20240131.v1"
        # mock do not have the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", "")
        executor_version = get_executor_version()
        assert executor_version == "promptflow-executor/0.0.1"

    def test_generate_error_response(self):
        non_pf_ex = ValueError("Test exception")
        base_ex = ExecutionTimeoutError(1)
        json_ser_ex = JsonSerializedPromptflowException(json.dumps(ExceptionPresenter.create(base_ex).to_dict()))

        non_pf_error_response = generate_error_response(non_pf_ex)
        assert non_pf_error_response.message == "Test exception"
        assert non_pf_error_response.response_code == ResponseCode.SERVICE_ERROR
        assert non_pf_error_response.innermost_error_code == "ValueError"

        base_error_response = generate_error_response(base_ex)
        assert base_error_response.message == "Execution timeout for exceeding 1 seconds"
        assert base_error_response.response_code == ResponseCode.CLIENT_ERROR
        assert base_error_response.innermost_error_code == "ExecutionTimeoutError"

        json_ser_error_response = generate_error_response(json_ser_ex)
        assert json_ser_error_response.message == "Execution timeout for exceeding 1 seconds"
        assert json_ser_error_response.response_code == ResponseCode.CLIENT_ERROR
        assert json_ser_error_response.innermost_error_code == "ExecutionTimeoutError"

    def test_set_environment_variables(self):
        execution_request = BaseExecutionRequest(**MOCK_REQUEST)
        execution_request.environment_variables = {
            "PF_TEST_ENV": "dummy_value",
        }
        set_environment_variables(execution_request)
        assert os.environ.get("PF_TEST_ENV") == "dummy_value"
