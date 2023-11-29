import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from mock import MagicMock
from ruamel.yaml import YAML

from promptflow import tool
from promptflow._core._errors import InputTypeMismatch, NotSupported, PackageToolNotFoundError
from promptflow._core.tools_manager import (
    BuiltinsManager,
    NodeSourcePathEmpty,
    ToolLoader,
    collect_package_tools,
    collect_package_tools_and_connections,
    gen_tool_by_source,
)
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestToolLoader:
    def test_load_tool_for_node_with_invalid_node(self):
        tool_loader = ToolLoader(working_dir="test_working_dir")
        node: Node = Node(name="test", tool="test_tool", inputs={}, type=ToolType.PYTHON)
        with pytest.raises(UserErrorException, match="Node test does not have source defined."):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type=ToolType.PYTHON, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError, match="Tool source type invalid_type for python tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type=ToolType.CUSTOM_LLM, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError, match="Tool source type invalid_type for custom_llm tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node)

        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type="invalid_type", source=ToolSource(type=ToolSourceType.Code)
        )
        with pytest.raises(NotImplementedError, match="Tool type invalid_type is not supported yet."):
            tool_loader.load_tool_for_node(node)

    def test_load_tool_for_package_node(self, mocker):
        package_tools = {"test_tool": Tool(name="test_tool", type=ToolType.PYTHON, inputs={}).serialize()}
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tools)
        tool_loader = ToolLoader(
            working_dir="test_working_dir", package_tool_keys=["promptflow._core.tools_manager.collect_package_tools"]
        )
        node: Node = Node(
            name="test",
            tool="test_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="test_tool"),
        )
        tool = tool_loader.load_tool_for_node(node)
        assert tool.name == "test_tool"

        node: Node = Node(
            name="test",
            tool="test_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="invalid_tool"),
        )
        msg = (
            "Package tool 'invalid_tool' is not found in the current environment. "
            "All available package tools are: ['test_tool']."
        )
        with pytest.raises(PackageToolNotFoundError) as ex:
            tool_loader.load_tool_for_node(node)
            assert str(ex.value) == msg

    def test_load_tool_for_package_node_with_legacy_tool_id(self, mocker):
        package_tools = {
            "new_tool_1": Tool(
                name="new tool 1", type=ToolType.PYTHON, inputs={}, deprecated_tools=["old_tool_1"]
            ).serialize(),
            "new_tool_2": Tool(
                name="new tool 1", type=ToolType.PYTHON, inputs={}, deprecated_tools=["old_tool_2"]
            ).serialize(),
            "old_tool_2": Tool(name="old tool 2", type=ToolType.PYTHON, inputs={}).serialize(),
        }
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tools)
        tool_loader = ToolLoader(working_dir="test_working_dir", package_tool_keys=list(package_tools.keys()))
        node_with_legacy_tool: Node = Node(
            name="test_legacy_tool",
            tool="old_tool_1",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="old_tool_1"),
        )
        assert tool_loader.load_tool_for_node(node_with_legacy_tool).name == "new tool 1"

        node_with_legacy_tool_but_in_package_tools: Node = Node(
            name="test_legacy_tool_but_in_package_tools",
            tool="old_tool_2",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Package, tool="old_tool_2"),
        )
        assert tool_loader.load_tool_for_node(node_with_legacy_tool_but_in_package_tools).name == "old tool 2"

    def test_load_tool_for_script_node(self):
        working_dir = Path(__file__).parent
        tool_loader = ToolLoader(working_dir=working_dir)
        file = "test_tools_manager.py"
        node: Node = Node(
            name="test",
            tool="sample_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Code, path=file),
        )
        tool = tool_loader.load_tool_for_node(node)
        assert tool.name == "sample_tool"


# This tool is for testing tools_manager.ToolLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input


@pytest.mark.unittest
class TestToolsManager:
    @pytest.mark.parametrize(
        "tool_source, tool_type, error_code, error_message",
        [
            (
                ToolSource(type=ToolSourceType.Package, tool="fake_name", path="fake_path"),
                None,
                PackageToolNotFoundError,
                "Package tool 'fake_name' is not found in the current environment. "
                f"Available package tools include: '{','.join(collect_package_tools().keys())}'. "
                "Please ensure that the required tool package is installed in current environment.",
            ),
            (
                ToolSource(tool="fake_name", path=None),
                ToolType.PYTHON,
                NodeSourcePathEmpty,
                "Invalid node definitions found in the flow graph. The node 'fake_name' is missing its source path. "
                "Please kindly add the source path for the node 'fake_name' in the YAML file "
                "and try the operation again.",
            ),
            (
                ToolSource(tool="fake_name", path=Path("test_tools_manager.py")),
                ToolType.CUSTOM_LLM,
                NotSupported,
                "The tool type custom_llm is currently not supported for generating tools using source code. "
                "Please choose from the available types: python,prompt,llm. "
                "If you need further assistance, kindly contact support.",
            ),
        ],
    )
    def test_gen_tool_by_source_error(self, tool_source, tool_type, error_code, error_message):
        working_dir = Path(__file__).parent
        with pytest.raises(error_code) as ex:
            gen_tool_by_source("fake_name", tool_source, tool_type, working_dir),
        assert str(ex.value) == error_message

    @pytest.mark.skip(reason="enable this test after the tool is ready")
    def test_collect_package_tools_if_node_source_tool_is_legacy(self):
        legacy_node_source_tools = ["content_safety_text.tools.content_safety_text_tool.analyze_text"]
        package_tools = collect_package_tools(legacy_node_source_tools)
        assert "promptflow.tools.azure_content_safety.analyze_text" in package_tools.keys()

    def test_collect_package_tools_and_connections(self, install_custom_tool_pkg):
        # Need to reload pkg_resources to get the latest installed tools
        import importlib

        import pkg_resources

        importlib.reload(pkg_resources)

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
