import pytest
import unittest

from promptflow.contracts.types import FilePath
from my_tool_package.tools.tool_with_file_path_input import my_tool


@pytest.fixture
def my_file_path_input() -> FilePath:
    my_file_path_input = FilePath(".\\test_utils\\hello_method.py")
    return my_file_path_input


class TestToolWithFilePathInput:
    def test_tool_with_file_path_input(self, my_file_path_input):
        result = my_tool(my_file_path_input, input_text="Microsoft")
        assert result == "Hello Microsoft"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
