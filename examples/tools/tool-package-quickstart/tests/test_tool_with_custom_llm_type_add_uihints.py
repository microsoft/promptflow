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


class TestToolWithCustomLLMTypeAddUIHints:
    def test_tool_with_custom_llm_type_add_uihints(self, my_custom_connection):
        result = my_tool(
            my_custom_connection,
            "my-endpoint-name",
            "my-api",
            0,
            "Hello {{text}}",
            text="Microsoft")
        assert result == "Hello Microsoft"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
