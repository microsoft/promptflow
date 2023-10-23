import pytest
import unittest

from my_tool_package.tools.tool_with_custom_strong_type_connection import MyCustomConnection, my_tool


@pytest.fixture
def my_custom_connection() -> MyCustomConnection:
    my_custom_connection = MyCustomConnection(
        {
            "api_key" : "my-api-key",
            "api_base" : "my-api-base"
        }
    )
    return my_custom_connection


class TestMyToolWithCustomStrongTypeConnection:
    def test_my_tool(self, my_custom_connection):
        result = my_tool(my_custom_connection, input_text="Microsoft")
        assert result == "Hello Microsoft"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
