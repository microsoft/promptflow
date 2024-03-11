import inspect
from typing import Union

import pytest

from promptflow._core._errors import DuplicateToolMappingError
from promptflow._utils.tool_utils import (
    DynamicListError,
    ListFunctionResponseError,
    RetrieveToolFuncResultValidationError,
    _find_deprecated_tools,
    append_workspace_triple_to_func_input_params,
    function_to_interface,
    load_function_from_function_path,
    param_to_definition,
    validate_dynamic_list_func_response_type,
    validate_tool_func_result,
)
from promptflow.connections import AzureOpenAIConnection, CustomConnection
from promptflow.contracts.tool import Tool, ToolFuncCallScenario, ToolType, ValueType


# mock functions for dynamic list function testing
def mock_dynamic_list_func1():
    pass


def mock_dynamic_list_func2(input1):
    pass


def mock_dynamic_list_func3(input1, input2):
    pass


def mock_dynamic_list_func4(input1, input2, **kwargs):
    pass


def mock_dynamic_list_func5(input1, input2, subscription_id):
    pass


def mock_dynamic_list_func6(input1, input2, subscription_id, resource_group_name, workspace_name):
    pass


def mock_dynamic_list_func7(input1, input2, subscription_id, **kwargs):
    pass


def mock_dynamic_list_func8(input1, input2, subscription_id, resource_group_name, workspace_name, **kwargs):
    pass


@pytest.mark.unittest
class TestToolUtils:
    def test_function_to_interface(self):
        def func(conn: [AzureOpenAIConnection, CustomConnection], input: [str, int]):
            pass

        input_defs, _, connection_types, _ = function_to_interface(func)
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

    def test_function_to_interface_with_kwargs(self):
        def func(input_str: str, **kwargs):
            pass

        _, _, _, enable_kwargs = function_to_interface(func)
        assert enable_kwargs is True

        def func(input_str: str):
            pass

        _, _, _, enable_kwargs = function_to_interface(func)
        assert enable_kwargs is False

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
            conn3: Union[MyFirstConnection, CustomConnection],
            conn4: Union[MyFirstConnection, MySecondConnection],
            conn5: CustomConnection,
            conn6: Union[CustomConnection, int],
            conn7: Union[MyFirstConnection, int],
        ):
            pass

        sig = inspect.signature(some_func)

        input_def, _ = param_to_definition(sig.parameters.get("conn1"), gen_custom_type_conn=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection"]

        input_def, _ = param_to_definition(sig.parameters.get("conn2"), gen_custom_type_conn=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection"]

        input_def, _ = param_to_definition(sig.parameters.get("conn3"), gen_custom_type_conn=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection"]

        input_def, _ = param_to_definition(sig.parameters.get("conn4"), gen_custom_type_conn=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type == ["MyFirstConnection", "MySecondConnection"]

        input_def, _ = param_to_definition(sig.parameters.get("conn5"), gen_custom_type_conn=True)
        assert input_def.type == ["CustomConnection"]
        assert input_def.custom_type is None

        input_def, _ = param_to_definition(sig.parameters.get("conn6"), gen_custom_type_conn=True)
        assert input_def.type == [ValueType.OBJECT]
        assert input_def.custom_type is None

        input_def, _ = param_to_definition(sig.parameters.get("conn7"), gen_custom_type_conn=True)
        assert input_def.type == [ValueType.OBJECT]
        assert input_def.custom_type is None

    @pytest.mark.parametrize(
        "func, func_input_params_dict, use_ws_triple, expected_res",
        [
            (mock_dynamic_list_func1, None, False, {}),
            (mock_dynamic_list_func2, {"input1": "value1"}, False, {"input1": "value1"}),
            (
                mock_dynamic_list_func3,
                {"input1": "value1", "input2": "value2"},
                False,
                {"input1": "value1", "input2": "value2"},
            ),
            (mock_dynamic_list_func3, {"input1": "value1"}, False, {"input1": "value1"}),
            (mock_dynamic_list_func3, {"input1": "value1"}, True, {"input1": "value1"}),
            (
                mock_dynamic_list_func4,
                {"input1": "value1"},
                True,
                {
                    "input1": "value1",
                    "subscription_id": "mock_subscription_id",
                    "resource_group_name": "mock_resource_group",
                    "workspace_name": "mock_workspace_name",
                },
            ),
            (
                mock_dynamic_list_func5,
                {"input1": "value1"},
                True,
                {"input1": "value1", "subscription_id": "mock_subscription_id"},
            ),
            (
                mock_dynamic_list_func5,
                {"input1": "value1", "subscription_id": "input_subscription_id"},
                True,
                {"input1": "value1", "subscription_id": "input_subscription_id"},
            ),
            (
                mock_dynamic_list_func6,
                {"input1": "value1"},
                True,
                {
                    "input1": "value1",
                    "subscription_id": "mock_subscription_id",
                    "resource_group_name": "mock_resource_group",
                    "workspace_name": "mock_workspace_name",
                },
            ),
            (
                mock_dynamic_list_func6,
                {
                    "input1": "value1",
                    "workspace_name": "input_workspace_name",
                },
                True,
                {
                    "input1": "value1",
                    "workspace_name": "input_workspace_name",
                    "subscription_id": "mock_subscription_id",
                    "resource_group_name": "mock_resource_group",
                },
            ),
            (
                mock_dynamic_list_func7,
                {"input1": "value1"},
                True,
                {
                    "input1": "value1",
                    "subscription_id": "mock_subscription_id",
                    "resource_group_name": "mock_resource_group",
                    "workspace_name": "mock_workspace_name",
                },
            ),
            (
                mock_dynamic_list_func7,
                {"input1": "value1", "subscription_id": "input_subscription_id"},
                True,
                {
                    "input1": "value1",
                    "subscription_id": "input_subscription_id",
                    "resource_group_name": "mock_resource_group",
                    "workspace_name": "mock_workspace_name",
                },
            ),
            (
                mock_dynamic_list_func8,
                {"input1": "value1"},
                True,
                {
                    "input1": "value1",
                    "subscription_id": "mock_subscription_id",
                    "resource_group_name": "mock_resource_group",
                    "workspace_name": "mock_workspace_name",
                },
            ),
            (
                mock_dynamic_list_func8,
                {
                    "input1": "value1",
                    "subscription_id": "input_subscription_id",
                    "resource_group_name": "input_resource_group",
                    "workspace_name": "input_workspace_name",
                },
                True,
                {
                    "input1": "value1",
                    "subscription_id": "input_subscription_id",
                    "resource_group_name": "input_resource_group",
                    "workspace_name": "input_workspace_name",
                },
            ),
        ],
    )
    def test_append_workspace_triple_to_func_input_params(
        self, func, func_input_params_dict, use_ws_triple, expected_res, mocked_ws_triple
    ):
        ws_triple_dict = mocked_ws_triple._asdict() if use_ws_triple else None
        func_sig_params = inspect.signature(func).parameters
        actual_combined_inputs = append_workspace_triple_to_func_input_params(
            func_sig_params=func_sig_params,
            func_input_params_dict=func_input_params_dict,
            ws_triple_dict=ws_triple_dict,
        )
        assert actual_combined_inputs == expected_res

    @pytest.mark.parametrize(
        "res",
        [
            (
                [
                    {
                        "value": "fig0",
                        "display_value": "My_fig0",
                        "hyperlink": "https://www.bing.com/search?q=fig0",
                        "description": "this is 0 item",
                    },
                    {
                        "value": "kiwi1",
                        "display_value": "My_kiwi1",
                        "hyperlink": "https://www.bing.com/search?q=kiwi1",
                        "description": "this is 1 item",
                    },
                ]
            ),
            ([{"value": "fig0"}, {"value": "kiwi1"}]),
            ([{"value": "fig0", "display_value": "My_fig0"}, {"value": "kiwi1", "display_value": "My_kiwi1"}]),
            (
                [
                    {"value": "fig0", "display_value": "My_fig0", "hyperlink": "https://www.bing.com/search?q=fig0"},
                    {
                        "value": "kiwi1",
                        "display_value": "My_kiwi1",
                        "hyperlink": "https://www.bing.com/search?q=kiwi1",
                    },
                ]
            ),
            ([{"value": "fig0", "hyperlink": "https://www.bing.com/search?q=fig0"}]),
            (
                [
                    {"value": "fig0", "display_value": "My_fig0", "description": "this is 0 item"},
                    {
                        "value": "kiwi1",
                        "display_value": "My_kiwi1",
                        "hyperlink": "https://www.bing.com/search?q=kiwi1",
                        "description": "this is 1 item",
                    },
                ]
            ),
        ],
    )
    def test_validate_dynamic_list_func_response_type(self, res):
        validate_dynamic_list_func_response_type(response=res, f="mock_func")

    @pytest.mark.parametrize(
        "res, err_msg",
        [
            (None, "mock_func response can not be None."),
            (["a", "b"], "mock_func response must be a list of dict. a is not a dict."),
            ({"a": "b"}, "mock_func response must be a list."),
            ([{"a": "b"}], "mock_func response dict must have 'value' key."),
            ([{"value": 1 + 2j}], "mock_func response dict value \\(1\\+2j\\) is not json serializable."),
        ],
    )
    def test_validate_dynamic_list_func_response_type_with_error(self, res, err_msg):
        error_message = (
            f"Unable to display list of items due to '{err_msg}'. \nPlease contact the tool "
            f"author/support team for troubleshooting assistance."
        )
        with pytest.raises(ListFunctionResponseError, match=error_message):
            validate_dynamic_list_func_response_type(response=res, f="mock_func")

    def test_load_function_from_function_path(self, mock_module_with_list_func):
        func_path = "my_tool_package.tools.tool_with_dynamic_list_input.my_list_func"
        tool_func = load_function_from_function_path(func_path)
        assert callable(tool_func)

    def test_load_function_from_script(self):
        func_path = f"{__file__}:mock_dynamic_list_func1"
        tool_func = load_function_from_function_path(func_path)
        assert callable(tool_func)

    def test_load_function_from_function_path_with_error(self, mock_module_with_list_func):
        func_path = "mock_func_path"
        with pytest.raises(
            DynamicListError,
            match="Unable to display list of items due to 'Failed to parse function from function path: "
            "'mock_func_path'. Expected format: format 'my_module.my_func'. Detailed error: not enough "
            "values to unpack \\(expected 2, got 1\\)'. \nPlease contact the tool author/support team for "
            "troubleshooting assistance.",
        ):
            load_function_from_function_path(func_path)

        func_path = "fake_tool_pkg.tools.tool_with_dynamic_list_input.my_list_func"
        with pytest.raises(
            DynamicListError,
            match="Unable to display list of items due to 'Failed to parse function from function path: "
            "'fake_tool_pkg.tools.tool_with_dynamic_list_input.my_list_func'. Expected format: format "
            "'my_module.my_func'. Detailed error: No module named 'fake_tool_pkg''. \nPlease contact the tool "
            "author/support team for troubleshooting assistance.",
        ):
            load_function_from_function_path(func_path)

        func_path = "my_tool_package.tools.tool_with_dynamic_list_input.my_field"
        with pytest.raises(
            DynamicListError,
            match="Unable to display list of items due to 'Failed to parse function from function path: "
            "'my_tool_package.tools.tool_with_dynamic_list_input.my_field'. Expected format: "
            "format 'my_module.my_func'. Detailed error: Unable to display list of items due to ''1' "
            "is not callable.'. \nPlease contact the tool author/support team for troubleshooting assistance.",
        ):
            load_function_from_function_path(func_path)

    @pytest.mark.parametrize(
        "func_call_scenario, result, err_msg",
        [
            (
                ToolFuncCallScenario.REVERSE_GENERATED_BY,
                "dummy_result",
                f"ToolFuncCallScenario {ToolFuncCallScenario.REVERSE_GENERATED_BY} response must be a dict. "
                f"dummy_result is not a dict.",
            ),
            (
                "dummy_scenario",
                "dummy_result",
                f"Invalid tool func call scenario: dummy_scenario. "
                f"Available scenarios are {list(ToolFuncCallScenario)}",
            ),
        ],
    )
    def test_validate_tool_func_result(self, func_call_scenario, result, err_msg):
        error_message = (
            f"Unable to retrieve tool func result due to '{err_msg}'. \nPlease contact the tool author/support team "
            f"for troubleshooting assistance."
        )
        with pytest.raises(RetrieveToolFuncResultValidationError) as e:
            validate_tool_func_result(func_call_scenario, result)
        assert error_message == str(e.value)

    def test_find_deprecated_tools(self):
        package_tools = {
            "new_tool_1": Tool(
                name="new tool 1", type=ToolType.PYTHON, inputs={}, deprecated_tools=["old_tool_1"]
            ).serialize(),
            "new_tool_2": Tool(
                name="new tool 1", type=ToolType.PYTHON, inputs={}, deprecated_tools=["old_tool_1"]
            ).serialize(),
        }
        with pytest.raises(DuplicateToolMappingError, match="secure operation"):
            _find_deprecated_tools(package_tools)
