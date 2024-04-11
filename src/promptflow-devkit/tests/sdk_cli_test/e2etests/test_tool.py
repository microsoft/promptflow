import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._core.tool import ToolProvider, tool
from promptflow._core.tool_meta_generator import ToolValidationError, _serialize_tool
from promptflow._sdk._pf_client import PFClient
from promptflow.entities import DynamicList, InputSetting
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
TOOL_ROOT = TEST_ROOT / "test_configs/tools"

_client = PFClient()


@pytest.mark.e2etest
class TestTool:
    def get_tool_meta(self, tool_path):
        module_name = f"test_tool.{Path(tool_path).stem}"

        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, tool_path)
        module = importlib.util.module_from_spec(spec)

        # Load the module's code
        spec.loader.exec_module(module)
        tools_meta, _ = _client.tools._generate_tool_meta(module)
        return tools_meta

    def test_python_tool_meta(self):
        tool_path = TOOL_ROOT / "python_tool.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.python_tool.PythonTool.python_tool": {
                "class_name": "PythonTool",
                "function": "python_tool",
                "inputs": {"connection": {"type": ["AzureOpenAIConnection"]}, "input1": {"type": ["string"]}},
                "module": "test_tool.python_tool",
                "name": "PythonTool.python_tool",
                "type": "python",
            },
            "test_tool.python_tool.my_python_tool": {
                "function": "my_python_tool",
                "inputs": {"input1": {"type": ["string"]}},
                "module": "test_tool.python_tool",
                "name": "python_tool",
                "type": "python",
            },
            "test_tool.python_tool.my_python_tool_without_name": {
                "function": "my_python_tool_without_name",
                "inputs": {"input1": {"type": ["string"]}},
                "module": "test_tool.python_tool",
                "name": "my_python_tool_without_name",
                "type": "python",
            },
        }
        assert tool_meta == expect_tool_meta

    def test_llm_tool_meta(self):
        tool_path = TOOL_ROOT / "custom_llm_tool.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.custom_llm_tool.my_tool": {
                "name": "My Custom LLM Tool",
                "type": "custom_llm",
                "inputs": {"connection": {"type": ["CustomConnection"]}},
                "description": "This is a tool to demonstrate the custom_llm tool type",
                "module": "test_tool.custom_llm_tool",
                "function": "my_tool",
                "enable_kwargs": True,
            },
            "test_tool.custom_llm_tool.TestCustomLLMTool.tool_func": {
                "name": "My Custom LLM Tool",
                "type": "custom_llm",
                "inputs": {"connection": {"type": ["AzureOpenAIConnection"]}, "api": {"type": ["string"]}},
                "description": "This is a tool to demonstrate the custom_llm tool type",
                "module": "test_tool.custom_llm_tool",
                "class_name": "TestCustomLLMTool",
                "function": "tool_func",
                "enable_kwargs": True,
            },
        }
        assert tool_meta == expect_tool_meta

    def test_invalid_tool_type(self):
        with pytest.raises(UserErrorException) as exception:

            @tool(name="invalid_tool_type", type="invalid_type")
            def invalid_tool_type():
                pass

        assert exception.value.message == "Tool type invalid_type is not supported yet."

    def test_tool_with_custom_connection(self):
        tool_path = TOOL_ROOT / "tool_with_custom_connection.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.tool_with_custom_connection.MyTool.my_tool": {
                "name": "My Second Tool",
                "type": "python",
                "inputs": {"connection": {"type": ["CustomConnection"]}, "input_text": {"type": ["string"]}},
                "description": "This is my second tool",
                "module": "test_tool.tool_with_custom_connection",
                "class_name": "MyTool",
                "function": "my_tool",
            }
        }
        assert tool_meta == expect_tool_meta

        tool_path = TOOL_ROOT / "tool_with_custom_strong_type_connection.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.tool_with_custom_strong_type_connection.my_tool": {
                "name": "Tool With Custom Strong Type Connection",
                "type": "python",
                "inputs": {
                    "connection": {"type": ["CustomConnection"], "custom_type": ["MyCustomConnection"]},
                    "input_text": {"type": ["string"]},
                },
                "description": "This is my tool with custom strong type connection.",
                "module": "test_tool.tool_with_custom_strong_type_connection",
                "function": "my_tool",
            }
        }
        assert tool_meta == expect_tool_meta

    def test_tool_with_input_settings(self):
        tool_path = TOOL_ROOT / "tool_with_dynamic_list_input.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.tool_with_dynamic_list_input.my_tool": {
                "description": "This is my tool with dynamic list input",
                "function": "my_tool",
                "inputs": {
                    "endpoint_name": {
                        "dynamic_list": {
                            "func_kwargs": [
                                {
                                    "default": "",
                                    "name": "prefix",
                                    "optional": True,
                                    "reference": "${inputs.input_prefix}",
                                    "type": ["string"],
                                }
                            ],
                            "func_path": "test_tool.tool_with_dynamic_list_input.list_endpoint_names",
                        },
                        "type": ["string"],
                    },
                    "input_prefix": {"type": ["string"]},
                    "input_text": {
                        "allow_manual_entry": True,
                        "dynamic_list": {
                            "func_kwargs": [
                                {
                                    "default": "",
                                    "name": "prefix",
                                    "optional": True,
                                    "reference": "${inputs.input_prefix}",
                                    "type": ["string"],
                                },
                                {"default": 10, "name": "size", "optional": True, "type": ["int"]},
                            ],
                            "func_path": "test_tool.tool_with_dynamic_list_input.my_list_func",
                        },
                        "is_multi_select": True,
                        "type": ["list"],
                    },
                },
                "module": "test_tool.tool_with_dynamic_list_input",
                "name": "My Tool with Dynamic List Input",
                "type": "python",
            }
        }
        assert tool_meta == expect_tool_meta

        tool_path = TOOL_ROOT / "tool_with_enabled_by_value.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.tool_with_enabled_by_value.my_tool": {
                "name": "My Tool with Enabled By Value",
                "type": "python",
                "inputs": {
                    "user_type": {"type": ["string"], "enum": ["student", "teacher"]},
                    "student_id": {"type": ["string"], "enabled_by": "user_type", "enabled_by_value": ["student"]},
                    "teacher_id": {"type": ["string"], "enabled_by": "user_type", "enabled_by_value": ["teacher"]},
                },
                "description": "This is my tool with enabled by value",
                "module": "test_tool.tool_with_enabled_by_value",
                "function": "my_tool",
            }
        }
        assert tool_meta == expect_tool_meta

    def test_dynamic_list_with_invalid_reference(self):
        def my_list_func(prefix: str, size: int = 10):
            pass

        # value in reference doesn't exist in tool inputs
        invalid_dynamic_list_setting = DynamicList(function=my_list_func, input_mapping={"prefix": "invalid_input"})
        input_settings = {
            "input_text": InputSetting(
                dynamic_list=invalid_dynamic_list_setting, allow_manual_entry=True, is_multi_select=True
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings,
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(ToolValidationError) as exception:
            _client.tools.validate(my_tool, raise_error=True)
        assert "Cannot find invalid_input in the tool inputs." in exception.value.message

        # invalid dynamic func input
        invalid_dynamic_list_setting = DynamicList(
            function=my_list_func, input_mapping={"invalid_input": "input_prefix"}
        )
        input_settings = {
            "input_text": InputSetting(
                dynamic_list=invalid_dynamic_list_setting, allow_manual_entry=True, is_multi_select=True
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings,
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(ToolValidationError) as exception:
            _client.tools.validate(my_tool, raise_error=True)
        assert "Cannot find invalid_input in the inputs of dynamic_list func" in exception.value.message

        # check required inputs of dynamic list func
        invalid_dynamic_list_setting = DynamicList(function=my_list_func, input_mapping={"size": "input_prefix"})
        input_settings = {
            "input_text": InputSetting(
                dynamic_list=invalid_dynamic_list_setting,
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings,
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(ToolValidationError) as exception:
            _client.tools.validate(my_tool, raise_error=True)
        assert "Missing required input(s) of dynamic_list function: ['prefix']" in exception.value.message

    def test_enabled_by_with_invalid_input(self):
        # value in enabled_by_value doesn't exist in tool inputs
        input1_settings = InputSetting(enabled_by="invalid_input")

        @tool(name="enabled_by_with_invalid_input", input_settings={"input1": input1_settings})
        def enabled_by_with_invalid_input(input1: str, input2: str):
            pass

        with pytest.raises(ToolValidationError) as exception:
            _client.tools.validate(enabled_by_with_invalid_input, raise_error=True)
        assert 'Cannot find the input \\"invalid_input\\"' in exception.value.message

    def test_tool_with_file_path_input(self):
        tool_path = TOOL_ROOT / "tool_with_file_path_input.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.tool_with_file_path_input.my_tool": {
                "name": "Tool with FilePath Input",
                "type": "python",
                "inputs": {"input_file": {"type": ["file_path"]}, "input_text": {"type": ["string"]}},
                "description": "This is a tool to demonstrate the usage of FilePath input",
                "module": "test_tool.tool_with_file_path_input",
                "function": "my_tool",
            }
        }
        assert expect_tool_meta == tool_meta

    def test_tool_with_generated_by_input(self):
        tool_path = TOOL_ROOT / "tool_with_generated_by_input.py"
        tool_meta = self.get_tool_meta(tool_path)
        with open(TOOL_ROOT / "expected_generated_by_meta.json", "r") as f:
            expect_tool_meta = json.load(f)
        assert expect_tool_meta == tool_meta

    def test_validate_tool_script(self):
        tool_script_path = TOOL_ROOT / "custom_llm_tool.py"
        result = _client.tools.validate(tool_script_path)
        assert result.passed

        tool_script_path = TOOL_ROOT / "tool_with_dynamic_list_input.py"
        result = _client.tools.validate(tool_script_path)
        assert result.passed

        tool_script_path = TOOL_ROOT / "tool_with_invalid_schema.py"
        result = _client.tools.validate(tool_script_path)
        assert "1 is not of type 'string'" in result.error_messages["invalid_schema_type"]
        tool_script_path = TOOL_ROOT / "tool_with_invalid_icon.py"
        result = _client.tools.validate(tool_script_path)
        assert (
            "Cannot provide both `icon` and `icon_light` or `icon_dark`." in result.error_messages["invalid_tool_icon"]
        )
        tool_script_path = TOOL_ROOT / "tool_with_invalid_enabled_by.py"
        result = _client.tools.validate(tool_script_path)
        assert (
            'Cannot find the input "invalid_input" for the enabled_by of teacher_id.'
            in result.error_messages["invalid_input_settings"]
        )
        assert (
            'Cannot find the input "invalid_input" for the enabled_by of student_id.'
            in result.error_messages["invalid_input_settings"]
        )
        assert all(str(tool_script_path) == item.location for item in result._errors)

        with pytest.raises(ToolValidationError):
            _client.tools.validate(TOOL_ROOT / "tool_with_invalid_schema.py", raise_error=True)

    def test_validate_tool_func(self):
        def load_module_by_path(source):
            module_name = Path(source).stem
            spec = importlib.util.spec_from_file_location(module_name, source)
            module = importlib.util.module_from_spec(spec)

            # Load the module's code
            spec.loader.exec_module(module)
            return module

        tool_script_path = TOOL_ROOT / "custom_llm_tool.py"
        module = load_module_by_path(tool_script_path)
        tool_func = getattr(module, "my_tool")
        result = _client.tools.validate(tool_func)
        assert result.passed

        tool_script_path = TOOL_ROOT / "tool_with_invalid_schema.py"
        module = load_module_by_path(tool_script_path)
        tool_func = getattr(module, "invalid_schema_type")
        result = _client.tools.validate(tool_func)
        assert "invalid_schema_type" in result.error_messages
        assert "1 is not of type 'string'" in result.error_messages["invalid_schema_type"]
        assert "invalid_schema_type" == result._errors[0].function_name
        assert str(tool_script_path) == result._errors[0].location

        with pytest.raises(ToolValidationError):
            _client.tools.validate(tool_func, raise_error=True)

    def test_validate_package_tool(self):
        package_tool_path = TOOL_ROOT / "tool_package"
        sys.path.append(str(package_tool_path.resolve()))

        import tool_package

        with patch("promptflow._sdk.operations._tool_operations.ToolOperations._is_package_tool", return_value=True):
            result = _client.tools.validate(tool_package)
        assert len(result._errors) == 4
        assert "1 is not of type 'string'" in result.error_messages["invalid_schema_type"]
        assert (
            "Cannot provide both `icon` and `icon_light` or `icon_dark`." in result.error_messages["invalid_tool_icon"]
        )
        assert (
            'Cannot find the input "invalid_input" for the enabled_by of teacher_id.'
            in result.error_messages["invalid_input_settings"]
        )
        assert (
            'Cannot find the input "invalid_input" for the enabled_by of student_id.'
            in result.error_messages["invalid_input_settings"]
        )

    def test_input_settings_with_undefined_fields(self):
        from promptflow._sdk.operations._tool_operations import ToolOperations

        input_settings = {
            "input_text": InputSetting(
                allow_manual_entry=True,
                is_multi_select=True,
                undefined_field1=1,
                undefined_field2=True,
                undefined_field3={"key": "value"},
                undefined_field4=[1, 2, 3],
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings,
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        tool_operation = ToolOperations()
        tool_obj, input_settings, extra_info = tool_operation._parse_tool_from_func(my_tool)
        construct_tool, validate_result = _serialize_tool(tool_obj, input_settings, extra_info)
        assert len(validate_result) == 0
        assert construct_tool["inputs"]["input_text"]["undefined_field1"] == 1
        assert construct_tool["inputs"]["input_text"]["undefined_field2"] is True
        assert construct_tool["inputs"]["input_text"]["undefined_field3"] == {"key": "value"}
        assert construct_tool["inputs"]["input_text"]["undefined_field4"] == [1, 2, 3]

    def test_validate_tool_class(self):
        from promptflow.tools.serpapi import SerpAPI

        result = _client.tools.validate(SerpAPI)
        assert result.passed

        class InvalidToolClass(ToolProvider):
            def __init__(self):
                super().__init__()

            @tool(name="My Custom Tool")
            def tool_func(self, api: str):
                pass

            @tool(name=1)
            def invalid_tool_func(self, api: str):
                pass

        result = _client.tools.validate(InvalidToolClass)
        assert not result.passed
        assert result._kwargs["total_count"] == 2
        assert result._kwargs["invalid_count"] == 1
        assert len(result._errors) == 1
        assert "1 is not of type 'string'" in result._errors[0].message

    def test_generate_tools_meta(self):
        flow_path = TEST_ROOT / "test_configs" / "flows" / "flow-with_tool_settings" / "flow.dag.yaml"
        tools_meta, errors = _client.flows._generate_tools_meta(flow=flow_path)
        assert "tool_with_input_settings.py" in tools_meta["code"]
        expect_tool_meta = {
            "type": "python",
            "inputs": {
                "user_type": {"type": ["string"], "enum": ["student", "teacher"]},
                "student_id": {
                    "type": ["string"],
                    "enabled_by": "user_type",
                    "enabled_by_value": ["student"],
                    "undefined_field": {"key": "value"},
                },
                "teacher_id": {"type": ["string"], "enabled_by": "user_type", "enabled_by_value": ["teacher"]},
            },
            "description": "tool with input settings",
            "source": "tool_with_input_settings.py",
            "function": "tool_with_input_settings",
            "unknown_key": "value",
        }
        assert expect_tool_meta == tools_meta["code"]["tool_with_input_settings.py"]
        assert "tool_with_invalid_input_settings.py" in errors
        expect_error_msg = 'Cannot find the input "invalid_input" for the enabled_by of teacher_id.'
        assert expect_error_msg in errors["tool_with_invalid_input_settings.py"]
