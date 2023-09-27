import pytest

from promptflow.exceptions import PromptflowException


@pytest.mark.unittest
class TestExceptions:
    def test_exception_message(self):
        ex = PromptflowException(
            message_format="Test exception message with parameters: {param}, {param1}.",
            param="test_param",
        )

        assert ex.message == "Test exception message with parameters: test_param, N/A."
