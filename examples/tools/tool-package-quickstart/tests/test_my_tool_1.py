import pytest
import unittest

from my_tool_package.connections import MyFirstConnection
from my_tool_package.tools.my_tool_1 import my_tool


@pytest.fixture
def my_custom_connection() -> MyFirstConnection:
    my_custom_connection = MyFirstConnection(api_key="my_api_key")
    return my_custom_connection


class TestMyTool1:
    def test_my_tool_1(self, my_custom_connection):
        result = my_tool(my_custom_connection, input_text="Hello Microsoft! ")
        print("result: ", result)
        assert result == "connection_value is MyFirstConnection: True"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
