import json
import os
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException, ResponseCode
from promptflow._utils.logger_utils import bulk_logger, flow_logger, logger, service_logger
from promptflow._version import VERSION as PF_VERSION
from promptflow.core._version import __version__ as PF_CORE_VERSION
from promptflow.executor._service._errors import ExecutionTimeoutError
from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest
from promptflow.executor._service.utils.service_utils import (
    generate_error_response,
    get_commit_id,
    get_log_context,
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

    def test_get_log_context_with_service_logger(self):
        request = FlowExecutionRequest(**MOCK_REQUEST)
        request.log_path = Path(mkdtemp()) / "log.txt"
        with get_log_context(request, enable_service_logger=True):
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
        operation_context = update_and_get_operation_context(context_dict)
        assert (
            operation_context.user_agent
            == f"dummy_user_agent promptflow/{PF_VERSION} promptflow-core/{PF_CORE_VERSION}"
        )
        assert operation_context.request_id == "dummy_request_id"

    def test_get_commit_id(self, monkeypatch):
        # mock have the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"commit_id": "test-commit-id"}')
        commit_id = get_commit_id()
        assert commit_id == "test-commit-id"
        # mock do not have the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", "")
        commit_id = get_commit_id()
        assert commit_id == "unknown"

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
        environment_variables = {
            "PF_TEST_ENV": "dummy_value",
        }
        set_environment_variables(environment_variables)
        assert os.environ.get("PF_TEST_ENV") == "dummy_value"
