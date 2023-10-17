import pytest
import unittest

from my_tool_package.tools.my_tool_with_custom_strong_type_connection import MyCustomConnection, my_tool


@pytest.fixture
def my_custom_connection() -> MyCustomConnection:
    my_custom_connection = MyCustomConnection(
        {
            "api_key" : "my-api-key",
            "api_url" : "my-api-url"
        }
    )
    return my_custom_connection


class TestMyToolWithCustomStrongTypeConnection:
    def test_my_tool(self, my_custom_connection):
        result = my_tool(my_custom_connection, input_param="fake_param")
        assert result == ""


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
