import pytest
import unittest

from promptflow.connections import CustomConnection
from my_tool_package.tools.tool_with_custom_llm_type import my_tool


@pytest.fixture
def my_custom_connection() -> CustomConnection:
    my_custom_connection = CustomConnection(
        {
            "api-key" : "my-api-key",
            "api-secret" : "my-api-secret",
            "api-url" : "my-api-url"
        }
    )
    return my_custom_connection


class TestToolWithCustomLLMType:
    def test_tool_with_custom_llm_type(self, my_custom_connection):
        result = my_tool(my_custom_connection, "Hello {{text}}", text="Microsoft")
        assert result == "Hello Microsoft"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
