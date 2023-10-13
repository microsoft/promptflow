import inspect
from typing import Union

import pytest

from promptflow._utils.tool_utils import function_to_interface, param_to_definition
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

    def test_param_to_definition(self):
        from promptflow._sdk.entities import CustomStrongTypeConnection
        from promptflow.contracts.tool import Secret

        class MyFirstConnection(CustomStrongTypeConnection):
            api_key: Secret
            api_base: str

        class MySecondConnection(CustomStrongTypeConnection):
            api_key: Secret
            api_base: str

        def some_func(
            conn1: MyFirstConnection,
            conn2: Union[CustomConnection, MyFirstConnection],
            conn3: Union[MyFirstConnection, MySecondConnection],
            conn4: CustomConnection,
            conn5: Union[CustomConnection, int],
            conn6: Union[MyFirstConnection, int],
        ):
            pass

        sig = inspect.signature(some_func)

        input_def, _ = param_to_definition(sig.parameters.get("conn1"), should_gen_custom_type=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection"]
        print(input_def)

        input_def, _ = param_to_definition(sig.parameters.get("conn2"), should_gen_custom_type=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection"]
        print(input_def)

        input_def, _ = param_to_definition(sig.parameters.get("conn3"), should_gen_custom_type=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection", "MySecondConnection"]
        print(input_def)

        input_def, _ = param_to_definition(sig.parameters.get("conn4"), should_gen_custom_type=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type is None

        input_def, _ = param_to_definition(sig.parameters.get("conn5"), should_gen_custom_type=True)
        assert input_def.type == [ValueType.OBJECT]
        assert input_def.custom_type is None

        input_def, _ = param_to_definition(sig.parameters.get("conn6"), should_gen_custom_type=True)
        assert input_def.type == [ValueType.OBJECT]
        assert input_def.custom_type is None
