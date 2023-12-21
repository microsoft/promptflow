import textwrap
from unittest.mock import patch

import pytest
from mock import MagicMock
from ruamel.yaml import YAML

from promptflow._core._errors import InputTypeMismatch
from promptflow._core.tools_manager import (
    BuiltinsManager,
    collect_package_tools,
    collect_package_tools_and_connections,
)
from promptflow.contracts.flow import InputAssignment, InputValueType


@pytest.mark.unittest
class TestToolsManager:
    def test_collect_package_tools_if_node_source_tool_is_legacy(self):
        legacy_node_source_tools = ["content_safety_text.tools.content_safety_text_tool.analyze_text"]
        package_tools = collect_package_tools(legacy_node_source_tools)
        assert "promptflow.tools.azure_content_safety.analyze_text" in package_tools.keys()

    def test_collect_package_tools_and_connections(self, install_custom_tool_pkg):
        yaml = YAML()
        yaml.preserve_quotes = True
        keys = ["my_tool_package.tools.my_tool_2.MyTool.my_tool"]
        tools, specs, templates = collect_package_tools_and_connections(keys)
        assert len(tools) == 1
        assert specs == {
            "my_tool_package.connections.MyFirstConnection": {
                "connectionCategory": "CustomKeys",
                "flowValueType": "CustomConnection",
                "connectionType": "MyFirstConnection",
                "ConnectionTypeDisplayName": "MyFirstConnection",
                "configSpecs": [
                    {"name": "api_key", "displayName": "Api Key", "configValueType": "Secret", "isOptional": False},
                    {"name": "api_base", "displayName": "Api Base", "configValueType": "str", "isOptional": True},
                ],
                "module": "my_tool_package.connections",
                "package": "test-custom-tools",
                "package_version": "0.0.2",
            }
        }

        expected_template = {
            "$schema": "https://azuremlschemas.azureedge.net/promptflow/latest/CustomStrongTypeConnection.schema.json",
            "name": "to_replace_with_connection_name",
            "type": "custom",
            "custom_type": "MyFirstConnection",
            "module": "my_tool_package.connections",
            "package": "test-custom-tools",
            "package_version": "0.0.2",
            "configs": {"api_base": "This is my first connection."},
            "secrets": {"api_key": "to_replace_with_api_key"},
        }
        loaded_yaml = yaml.load(templates["my_tool_package.connections.MyFirstConnection"])
        assert loaded_yaml == expected_template

        keys = ["my_tool_package.tools.my_tool_with_custom_strong_type_connection.my_tool"]
        tools, specs, templates = collect_package_tools_and_connections(keys)
        assert len(templates) == 1
        expected_template = """
            name: "to_replace_with_connection_name"
            type: custom
            custom_type: MyCustomConnection
            module: my_tool_package.tools.my_tool_with_custom_strong_type_connection
            package: test-custom-tools
            package_version: 0.0.2
            configs:
              api_url: "This is a fake api url."  # String type. The api url.
            secrets:      # must-have
              api_key: "to_replace_with_api_key"  # String type. The api key.
            """

        content = templates["my_tool_package.tools.my_tool_with_custom_strong_type_connection.MyCustomConnection"]
        expected_template_str = textwrap.dedent(expected_template)
        assert expected_template_str in content

    def test_gen_dynamic_list(self, mocked_ws_triple, mock_module_with_list_func):
        from promptflow._sdk._utils import _gen_dynamic_list

        func_path = "my_tool_package.tools.tool_with_dynamic_list_input.my_list_func"
        func_kwargs = {"prefix": "My"}
        result = _gen_dynamic_list({"func_path": func_path, "func_kwargs": func_kwargs})
        assert len(result) == 2

        # test gen_dynamic_list with ws_triple.
        with patch("promptflow._cli._utils.get_workspace_triad_from_local", return_value=mocked_ws_triple):
            result = _gen_dynamic_list({"func_path": func_path, "func_kwargs": func_kwargs})
            assert len(result) == 2


@pytest.mark.unittest
class TestBuiltinsManager:
    def test_load_tool_from_module(
        self,
    ):
        # Test case 1: When class_name is None
        module = MagicMock()
        tool_name = "test_tool"
        module_name = "test_module"
        class_name = None
        method_name = "test_method"
        node_inputs = {"input1": InputAssignment(value_type=InputValueType.LITERAL, value="value1")}

        # Mock the behavior of the module and class
        module.test_method = MagicMock()

        # Call the method
        api, init_inputs = BuiltinsManager._load_tool_from_module(
            module, tool_name, module_name, class_name, method_name, node_inputs
        )

        # Assertions
        assert api == module.test_method
        assert init_inputs == {}

        # Non literal input for init parameter will raise exception.
        module = MagicMock()
        tool_name = "test_tool"
        module_name = "test_module"
        class_name = "TestClass"
        method_name = "test_method"
        node_inputs = {"input1": InputAssignment(value_type=InputValueType.FLOW_INPUT, value="value1")}

        # Mock the behavior of the module and class
        module.TestClass = MagicMock()
        module.TestClass.get_initialize_inputs = MagicMock(return_value=["input1"])
        module.TestClass.get_required_initialize_inputs = MagicMock(return_value=["input1"])
        module.TestClass.test_method = MagicMock()

        # Call the method
        with pytest.raises(InputTypeMismatch) as ex:
            BuiltinsManager._load_tool_from_module(module, tool_name, module_name, class_name, method_name, node_inputs)
        expected_message = (
            "Invalid input for 'test_tool': Initialization input 'input1' requires a literal value, "
            "but ${flow.value1} was received."
        )
        assert expected_message == str(ex.value)
