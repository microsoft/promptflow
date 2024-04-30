import importlib
import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from mock import MagicMock

from promptflow import tool
from promptflow._core._errors import InputTypeMismatch, InvalidSource, PackageToolNotFoundError
from promptflow._core.tools_manager import (
    BuiltinsManager,
    ToolLoader,
    collect_package_tools,
    collect_package_tools_and_connections,
)
from promptflow._utils.yaml_utils import load_yaml_string
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool, ToolFuncCallScenario, ToolType
from promptflow.exceptions import UserErrorException


@pytest.fixture
def mock_entry_point():
    from ...package_tools.custom_llm_tool_multi_inputs_without_index.list import list_package_tools

    entry_point = MagicMock()
    entry_point.load.return_value = list_package_tools
    entry_point.dist.metadata.return_value = "TestCustomLLMTool"
    entry_point.dist.version.return_value = "0.0.1"
    return entry_point


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

    @pytest.mark.parametrize(
        "source_path, error_message",
        [
            (None, "Load tool failed for node 'test'. The source path is 'None'."),
            ("invalid_file.py", "Load tool failed for node 'test'. Tool file 'invalid_file.py' can not be found."),
        ],
    )
    def test_load_tool_for_script_node_exception(self, source_path, error_message):
        working_dir = Path(__file__).parent
        tool_loader = ToolLoader(working_dir=working_dir)
        node: Node = Node(
            name="test",
            tool="sample_tool",
            inputs={},
            type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Code, path=source_path),
        )
        with pytest.raises(InvalidSource) as ex:
            tool_loader.load_tool_for_script_node(node)
        assert str(ex.value) == error_message


# This tool is for testing tools_manager.ToolLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input


@pytest.mark.unittest
@pytest.mark.usefixtures("recording_injection")
class TestToolsManager:
    def test_collect_package_tools_if_node_source_tool_is_legacy(self):
        legacy_node_source_tools = ["content_safety_text.tools.content_safety_text_tool.analyze_text"]
        package_tools = collect_package_tools(legacy_node_source_tools)
        assert "promptflow.tools.azure_content_safety.analyze_text" in package_tools.keys()

    def test_collect_package_tools_set_defaut_input_index(self, mocker, mock_entry_point):
        entry_point = mock_entry_point
        entry_points = (entry_point,)
        mocker.patch("promptflow._core.tools_manager._get_entry_points_by_group", return_value=entry_points)
        mocker.patch.object(importlib, "import_module", return_value=MagicMock())
        tool = "custom_llm_tool.TestCustomLLMTool.call"
        package_tools = collect_package_tools([tool])
        inputs_order = [
            "connection",
            "deployment_name",
            "api",
            "temperature",
            "top_p",
            "max_tokens",
            "stop",
            "presence_penalty",
            "frequency_penalty",
        ]
        for index, input_name in enumerate(inputs_order):
            assert package_tools[tool]["inputs"][input_name]["ui_hints"]["index"] == index

    def test_collect_package_tools_and_connections_set_defaut_input_index(self, mocker, mock_entry_point):
        entry_point = mock_entry_point
        entry_points = (entry_point,)
        mocker.patch("promptflow._core.tools_manager._get_entry_points_by_group", return_value=entry_points)
        mocker.patch.object(importlib, "import_module", return_value=MagicMock())
        tool = "custom_llm_tool.TestCustomLLMTool.call"
        package_tools, _, _ = collect_package_tools_and_connections([tool])
        inputs_order = [
            "connection",
            "deployment_name",
            "api",
            "temperature",
            "top_p",
            "max_tokens",
            "stop",
            "presence_penalty",
            "frequency_penalty",
        ]
        for index, input_name in enumerate(inputs_order):
            assert package_tools[tool]["inputs"][input_name]["ui_hints"]["index"] == index

    def test_collect_package_tools_and_connections(self, install_custom_tool_pkg):
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
        loaded_yaml = load_yaml_string(templates["my_tool_package.connections.MyFirstConnection"])
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

    def test_retrieve_tool_func_result_dynamic_list_scenario(
        self, mocked_ws_triple, mock_module_with_for_retrieve_tool_func_result
    ):
        from promptflow._sdk._utilities.general_utils import _retrieve_tool_func_result

        func_path = "my_tool_package.tools.tool_with_dynamic_list_input.my_list_func"
        func_kwargs = {"prefix": "My"}
        result = _retrieve_tool_func_result(
            ToolFuncCallScenario.DYNAMIC_LIST, {"func_path": func_path, "func_kwargs": func_kwargs}
        )
        assert len(result) == 2

        # test retrieve tool func result with ws_triple.
        with patch("promptflow._cli._utils.get_workspace_triad_from_local", return_value=mocked_ws_triple):
            result = _retrieve_tool_func_result(
                ToolFuncCallScenario.DYNAMIC_LIST, {"func_path": func_path, "func_kwargs": func_kwargs}
            )

    @pytest.mark.parametrize(
        "func_call_scenario, func_path, func_kwargs, expected",
        [
            (
                ToolFuncCallScenario.DYNAMIC_LIST,
                "my_tool_package.tools.tool_with_dynamic_list_input.my_list_func",
                {"prefix": "My"},
                list,
            ),
            (
                ToolFuncCallScenario.GENERATED_BY,
                "my_tool_package.tools.tool_with_generated_by_input.generated_by_func",
                {"index_type": "Azure Cognitive Search"},
                str,
            ),
            (
                ToolFuncCallScenario.REVERSE_GENERATED_BY,
                "my_tool_package.tools.tool_with_generated_by_input.reverse_generated_by_func",
                {"index_json": json.dumps({"index_type": "Azure Cognitive Search", "index": "index_1"})},
                dict,
            ),
        ],
    )
    def test_retrieve_tool_func_result(
        self,
        func_call_scenario,
        func_path,
        func_kwargs,
        expected,
        mocked_ws_triple,
        mock_module_with_for_retrieve_tool_func_result,
    ):
        from promptflow._sdk._utilities.general_utils import _retrieve_tool_func_result

        result = _retrieve_tool_func_result(func_call_scenario, {"func_path": func_path, "func_kwargs": func_kwargs})
        assert isinstance(result["result"], expected)

        # test retrieve tool func result with ws_triple.
        with patch("promptflow._cli._utils.get_workspace_triad_from_local", return_value=mocked_ws_triple):
            result = _retrieve_tool_func_result(
                func_call_scenario, {"func_path": func_path, "func_kwargs": func_kwargs}
            )
            assert isinstance(result["result"], expected)

    @pytest.mark.parametrize(
        "func_call_scenario, func_path, func_kwargs, expected",
        [
            (
                "dummy_senario",
                "my_tool_package.tools.tool_with_generated_by_input.reverse_generated_by_func",
                {"index_json": json.dumps({"index_type": "Azure Cognitive Search", "index": "index_1"})},
                f"Invalid tool func call scenario: dummy_senario. "
                f"Available scenarios are {list(ToolFuncCallScenario)}",
            ),
            (
                ToolFuncCallScenario.REVERSE_GENERATED_BY,
                "my_tool_package.tools.tool_with_generated_by_input.generated_by_func",
                {"index_type": "Azure Cognitive Search"},
                "ToolFuncCallScenario reverse_generated_by response must be a dict.",
            ),
        ],
    )
    def test_retrieve_tool_func_result_error(
        self,
        func_call_scenario,
        func_path,
        func_kwargs,
        expected,
        mocked_ws_triple,
        mock_module_with_for_retrieve_tool_func_result,
    ):
        from promptflow._sdk._utilities.general_utils import _retrieve_tool_func_result

        with pytest.raises(Exception) as e:
            _retrieve_tool_func_result(func_call_scenario, {"func_path": func_path, "func_kwargs": func_kwargs})
        assert expected in str(e.value)

    def test_register_apis(self):
        from typing import Union

        from promptflow._core.tool import ToolProvider
        from promptflow._core.tools_manager import connection_type_to_api_mapping, register_apis
        from promptflow.connections import AzureOpenAIConnection, OpenAIConnection, ServerlessConnection

        class MockAI1(ToolProvider):
            def __init__(self, input: str, connection: Union[OpenAIConnection, ServerlessConnection]):
                super().__init__()

        class MockAI2(ToolProvider):
            def __init__(self, connection: AzureOpenAIConnection):
                super().__init__()

        register_apis(MockAI1)
        register_apis(MockAI2)

        assert len(connection_type_to_api_mapping) == 3


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
