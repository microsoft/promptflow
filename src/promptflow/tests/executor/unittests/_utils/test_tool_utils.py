import pytest

from promptflow._utils.tool_utils import function_to_interface
from promptflow.connections import AzureOpenAIConnection, CustomConnection
from promptflow.contracts.tool import ValueType


@pytest.mark.unittest
class TestToolUtils:
    def test_function_to_interface(self):
        def func(conn: [AzureOpenAIConnection, CustomConnection], input: [str, int]):
            pass

        input_defs, _, connection_types = function_to_interface(func)
        assert len(input_defs) == 2
        assert input_defs["conn"].type == ["AzureOpenAIConnection", "CustomConnection"]
        assert input_defs["input"].type == [ValueType.OBJECT]
        assert connection_types == [["AzureOpenAIConnection", "CustomConnection"]]

    def test_function_to_interface_with_invalid_initialize_inputs(self):
        def func(input_str: str):
            pass

        with pytest.raises(Exception) as exec_info:
            function_to_interface(func, {"input_str": "test"})
        assert "Duplicate inputs found from" in exec_info.value.args[0]
