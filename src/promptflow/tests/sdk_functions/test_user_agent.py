import os
import pytest
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._constants import USER_AGENT


@pytest.mark.e2etest
class TestUserAgent:
    def test_user_agent(self) -> None:
        os.environ[USER_AGENT] = "perf_monitor/1.0"
        context = OperationContext.get_instance()
        assert "perf_monitor/1.0" in context.get_user_agent()
