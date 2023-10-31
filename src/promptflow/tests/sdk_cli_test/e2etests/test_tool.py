import importlib.util
from pathlib import Path

import pytest
from promptflow._core.tool import tool
from promptflow.entities import DynamicList, InputSetting
from promptflow._sdk._pf_client import PFClient
from promptflow.exceptions import UserErrorException

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."
TEST_ROOT = Path(__file__).parent.parent.parent
TOOL_ROOT = TEST_ROOT / "test_configs/tools"

_client = PFClient()


@pytest.mark.e2etest
class TestCli:
    def get_tool_meta(self, tool_path):
        module_name = f"test_tool.{Path(tool_path).stem}"

        # Load the module from the file path
        spec = importlib.util.spec_from_file_location(module_name, tool_path)
        module = importlib.util.module_from_spec(spec)

        # Load the module's code
        spec.loader.exec_module(module)
        return _client._tools.generate_tool_meta(module)

    def test_python_tool_meta(self):
        tool_path = TOOL_ROOT / "python_tool.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            "test_tool.python_tool.PythonTool.python_tool": {
                "class_name": "PythonTool",
                "function": "python_tool",
                "inputs": {
                    "connection": {"type": ["AzureOpenAIConnection"]},
                    "input1": {"type": ["string"]}
                },
                "module": "test_tool.python_tool",
                "name": "PythonTool.python_tool",
                "type": "python",
            },
            "test_tool.python_tool.my_python_tool": {
                "function": "my_python_tool",
                "inputs": {
                    "input1": {"type": ["string"]}
                },
                "module": "test_tool.python_tool",
                "name": "python_tool",
                "type": "python",
            },
            "test_tool.python_tool.my_python_tool_without_name": {
                "function": "my_python_tool_without_name",
                "inputs": {
                    "input1": {"type": ["string"]}
                },
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
            'test_tool.custom_llm_tool.my_tool': {
                'name': 'My Custom LLM Tool',
                'type': 'custom_llm',
                'inputs': {
                    'connection': {'type': ['CustomConnection']}
                },
                'description': 'This is a tool to demonstrate the custom_llm tool type',
                'module': 'test_tool.custom_llm_tool',
                'function': 'my_tool'
            },
            'test_tool.custom_llm_tool.TestCustomLLMTool.tool_func': {
                'name': 'My Custom LLM Tool',
                'type': 'custom_llm',
                'inputs': {
                    'connection': {'type': ['AzureOpenAIConnection']},
                    'api': {'type': ['string']}
                },
                'description': 'This is a tool to demonstrate the custom_llm tool type',
                'module': 'test_tool.custom_llm_tool',
                'class_name': 'TestCustomLLMTool',
                'function': 'tool_func'
            }
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
                "inputs": {
                    "connection": {"type": ["CustomConnection"]},
                    "input_text": {"type": ["string"]}
                },
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
                "name": "My Tool with Dynamic List Input",
                "type": "python",
                "inputs": {
                    "input_text": {
                        "type": ["list"],
                        "is_multi_select": True,
                        "allow_manual_entry": True,
                        "dynamic_list": {
                            "func_path": "test_tool.tool_with_dynamic_list_input.my_list_func",
                            "func_kwargs": [
                                {
                                    "name": "prefix",
                                    "type": ["string"],
                                    "reference": "${inputs.input_prefix}",
                                    "optional": True,
                                    "default": "",
                                },
                                {
                                    "name": "size",
                                    "type": ["int"],
                                    "optional": True,
                                    "default": 10
                                },
                            ],
                        },
                    },
                    "input_prefix": {"type": ["string"]},
                },
                "description": "This is my tool with dynamic list input",
                "module": "test_tool.tool_with_dynamic_list_input",
                "function": "my_tool",
            }
        }
        assert tool_meta == expect_tool_meta

        tool_path = TOOL_ROOT / "tool_with_enabled_by_value.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            'test_tool.tool_with_enabled_by_value.my_tool': {
                'name': 'My Tool with Enabled By Value',
                'type': 'python',
                'inputs': {
                    'user_type': {'type': ['string']},
                    'student_id': {'type': ['string']},
                    'teacher_id': {
                        'type': ['string'],
                        'enabled_by': 'user_type',
                        'enabled_by_value': ['teacher']
                    }
                },
                'description': 'This is my tool with enabled by value',
                'module': 'test_tool.tool_with_enabled_by_value',
                'function': 'my_tool'
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
                dynamic_list=invalid_dynamic_list_setting,
                allow_manual_entry=True,
                is_multi_select=True
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(UserErrorException) as exception:
            _client._tools._serialize_tool(my_tool)
        assert "Cannot find invalid_input in the tool inputs." in exception.value.message

        # invalid dynamic func input
        invalid_dynamic_list_setting = DynamicList(
            function=my_list_func, input_mapping={"invalid_input": "input_prefix"})
        input_settings = {
            "input_text": InputSetting(
                dynamic_list=invalid_dynamic_list_setting,
                allow_manual_entry=True,
                is_multi_select=True
            )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(UserErrorException) as exception:
            _client._tools._serialize_tool(my_tool)
        assert "Cannot find invalid_input in the inputs of dynamic_list func" in exception.value.message

        # check required inputs of dynamic list func
        invalid_dynamic_list_setting = DynamicList(function=my_list_func, input_mapping={"size": "input_prefix"})
        input_settings = {
            "input_text": InputSetting(dynamic_list=invalid_dynamic_list_setting, )
        }

        @tool(
            name="My Tool with Dynamic List Input",
            description="This is my tool with dynamic list input",
            input_settings=input_settings
        )
        def my_tool(input_text: list, input_prefix: str) -> str:
            return f"Hello {input_prefix} {','.join(input_text)}"

        with pytest.raises(UserErrorException) as exception:
            _client._tools._serialize_tool(my_tool)
        assert "Missing required input(s) of dynamic_list function: ['prefix']" in exception.value.message

    def test_enabled_by_with_invalid_input(self):
        # value in enabled_by_value doesn't exist in tool inputs
        input1_settings = InputSetting(enabled_by="invalid_input")

        @tool(name="enabled_by_with_invalid_input", input_settings={"input1": input1_settings})
        def enabled_by_with_invalid_input(input1: str, input2: str):
            pass

        with pytest.raises(UserErrorException) as exception:
            _client._tools._serialize_tool(enabled_by_with_invalid_input)
        assert "Cannot find the input \"invalid_input\"" in exception.value.message

    def test_tool_with_file_path_input(self):
        tool_path = TOOL_ROOT / "tool_with_file_path_input.py"
        tool_meta = self.get_tool_meta(tool_path)
        expect_tool_meta = {
            'test_tool.tool_with_file_path_input.my_tool': {
                'name': 'Tool with FilePath Input',
                'type': 'python',
                'inputs': {
                    'input_file': {'type': ['file_path']},
                    'input_text': {'type': ['string']}
                },
                'description': 'This is a tool to demonstrate the usage of FilePath input',
                'module': 'test_tool.tool_with_file_path_input',
                'function': 'my_tool'
            }
        }
        assert expect_tool_meta == tool_meta
