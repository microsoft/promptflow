import pytest

from promptflow.storage.exceptions import to_string


@pytest.mark.unittest
class TestExceptions:
    def test_exception_to_string(self):
        class CustomException(Exception):
            pass

        ex = CustomException("Custom error message")
        expected_result = "CustomException: Custom error message"
        result = to_string(ex)
        assert result == expected_result

        ex = ValueError("Invalid value")
        expected_result = "ValueError: Invalid value"
        result = to_string(ex)
        assert result == expected_result
