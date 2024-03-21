import pytest

from promptflow._constants import ICON, ICON_LIGHT
from promptflow._core.tool import DynamicList, InputSetting, tool
from promptflow._core.tool_meta_generator import _parse_tool_from_function
from promptflow._core.tool_validation import _validate_tool_function, _validate_tool_schema


@tool()
def script_tool(input_param: str):
    print(input_param)


@pytest.mark.unittest
class TestToolValidation:
    def test_validate_tool_function(self):
        def mock_dynamic_list_func(input_prefix: str):
            pass

        tool = _parse_tool_from_function(script_tool, gen_custom_type_conn=True, skip_prompt_template=True)
        validation_result = _validate_tool_function(tool, {}, {})
        assert len(validation_result) == 0

        extra_info = {ICON: "icon/path", ICON_LIGHT: "icon/path"}

        invalid_dynamic_list_setting = DynamicList(
            function=mock_dynamic_list_func, input_mapping={"invalid_input": "input_prefix"}
        )
        input_settings = {
            "invalid_input_param": InputSetting(),
            "input_param": InputSetting(
                dynamic_list=invalid_dynamic_list_setting, allow_manual_entry=True, is_multi_select=True
            ),
        }
        validation_result = _validate_tool_function(tool, input_settings, extra_info)
        assert len(validation_result) == 5
        assert "Cannot provide both `icon` and `icon_light` or `icon_dark`." in validation_result
        assert "Cannot find invalid_input_param in tool inputs." in validation_result
        assert "Cannot find input_prefix in the tool inputs." in validation_result
        assert "Missing required input(s) of dynamic_list function: ['input_prefix']" in validation_result
        assert (
            f"Cannot find invalid_input in the inputs of dynamic_list func "
            f"{mock_dynamic_list_func.__module__}.{mock_dynamic_list_func.__name__}" in validation_result
        )

    def test_validate_tool_schema(self):
        tool_dict = {
            "function": "my_python_tool",
            "inputs": {"input1": {"type": ["string"]}},
            "name": "python_tool",
            "type": "python",
        }
        validate_result = _validate_tool_schema(tool_dict)
        assert validate_result is None

        # invalid tool dict
        invalid_tool_dict = {
            "function": "my_python_tool",
            "inputs": {"input1": {"type": ["string"]}},
            "name": 1,
            "type": "python",
        }
        validate_result = _validate_tool_schema(invalid_tool_dict)
        assert "1 is not of type 'string'" in validate_result
