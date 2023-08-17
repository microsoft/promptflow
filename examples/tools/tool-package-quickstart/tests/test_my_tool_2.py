import pytest
import unittest

from promptflow.connections import CustomConnection
from my_tool_package.tools.my_tool_2 import MyTool


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


@pytest.fixture
def my_tool_provider(my_custom_connection) -> MyTool:
    my_tool_provider = MyTool(my_custom_connection)
    return my_tool_provider


class TestMyTool2:
    def test_my_tool_2(self, my_tool_provider: MyTool):
        result = my_tool_provider.my_tool(input_text="Microsoft")
        assert result == "Hello Microsoft"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
