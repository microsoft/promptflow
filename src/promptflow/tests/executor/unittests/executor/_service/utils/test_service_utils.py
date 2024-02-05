import os

import pytest

from promptflow._core.operation_context import OperationContext
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest
from promptflow.executor._service.utils.service_utils import (
    get_executor_version,
    set_environment_variables,
    update_operation_context,
)

from ..contracts.test_execution_request import MOCK_REQUEST


@pytest.mark.unittest
class TestServiceUtils:
    def test_update_operation_context(self, monkeypatch):
        headers = {
            "context-user-agent": "dummy_user_agent",
            "context-request-id": "dummy_request_id",
        }
        # mock the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"build_number": "20240131.v1"}')

        update_operation_context(headers)
        operation_context = OperationContext.get_instance()
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

    def test_set_environment_variables(self):
        execution_request = BaseExecutionRequest(**MOCK_REQUEST)
        execution_request.environment_variables = {
            "PF_TEST_ENV": "dummy_value",
        }
        set_environment_variables(execution_request)
        assert os.environ.get("PF_TEST_ENV") == "dummy_value"
