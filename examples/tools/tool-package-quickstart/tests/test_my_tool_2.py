import pytest
import unittest

from my_tool_package.connections import MySecondConnection
from my_tool_package.tools.my_tool_2 import MyTool


@pytest.fixture
def my_custom_connection() -> MySecondConnection:
    my_custom_connection = MySecondConnection(api_key="my_api_key")
    return my_custom_connection


@pytest.fixture
def my_tool_provider(my_custom_connection) -> MyTool:
    my_tool_provider = MyTool(my_custom_connection)
    return my_tool_provider


class TestMyTool2:
    def test_my_tool_2(self, my_tool_provider: MyTool):
        result = my_tool_provider.my_tool(input_text="Hello Microsoft! ")
        assert result == "Hello Microsoft! This is my second connection."


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
