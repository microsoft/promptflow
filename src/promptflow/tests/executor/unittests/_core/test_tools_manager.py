from pathlib import Path

import pytest

from promptflow import tool
from promptflow._core._errors import PackageToolNotFoundError
from promptflow._core.tools_manager import APINotFound, ToolLoader
from promptflow.contracts.flow import Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestToolLoader:
    def test_load_tool_for_node_with_invalid_node(self):
        tool_loader = ToolLoader()
        working_dir = "test_working_dir"
        node: Node = Node(name="test", tool="test_tool", inputs={}, type=ToolType.PYTHON)
        with pytest.raises(UserErrorException, match="Node test does not have source defined."):
            tool_loader.load_tool_for_node(node, working_dir)

        node: Node = Node(
            name="test", tool="test_tool", inputs={},
            type=ToolType.PYTHON, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError,
            match="Tool source type invalid_type for python tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node, working_dir)

        node: Node = Node(
            name="test", tool="test_tool", inputs={},
            type=ToolType.CUSTOM_LLM, source=ToolSource(type="invalid_type")
        )
        with pytest.raises(
            NotImplementedError,
            match="Tool source type invalid_type for custom_llm tool is not supported yet."
        ):
            tool_loader.load_tool_for_node(node, working_dir)

        node: Node = Node(
            name="test", tool="test_tool", inputs={},
            type="invalid_type", source=ToolSource(type=ToolSourceType.Code)
        )
        with pytest.raises(NotImplementedError, match="Tool type invalid_type is not supported yet."):
            tool_loader.load_tool_for_node(node, working_dir)

    def test_load_tool_for_package_node(self, mocker):
        working_dir = "test_working_dir"
        package_tools = {"test_tool": Tool(name="test_tool", type=ToolType.PYTHON, inputs={}).serialize()}
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tools)
        tool_loader = ToolLoader(package_tool_keys=["promptflow._core.tools_manager.collect_package_tools"])
        node: Node = Node(
            name="test", tool="test_tool", inputs={},
            type=ToolType.PYTHON, source=ToolSource(type=ToolSourceType.Package, tool="test_tool")
        )
        tool = tool_loader.load_tool_for_node(node, working_dir)
        assert tool.name == "test_tool"

        node: Node = Node(
            name="test", tool="test_tool", inputs={},
            type=ToolType.PYTHON, source=ToolSource(type=ToolSourceType.Package, tool="invalid_tool")
        )
        msg = (
            "Package tool 'invalid_tool' is not found in the current environment. "
            "All available package tools are: ['test_tool']."
        )
        with pytest.raises(PackageToolNotFoundError) as ex:
            tool_loader.load_tool_for_node(node, working_dir)
            assert str(ex.value) == msg

    def test_load_tool_for_llm_node(self):
        tool_loader = ToolLoader()
        node: Node = Node(
            name="test", tool="test_tool", inputs={}, type=ToolType.LLM,
            provider="Test", api="invalid_api",
            source=ToolSource(type=ToolSourceType.Package, tool="test_tool"))
        with pytest.raises(APINotFound, match="The API 'Test.invalid_api' is not found."):
            tool_loader.load_tool_for_node(node, "test_working_dir")

    def test_load_tool_for_script_node(self):
        tool_loader = ToolLoader()
        working_dir = Path(__file__).parent
        file = "test_tools_manager.py"
        node: Node = Node(
            name="test", tool="sample_tool", inputs={}, type=ToolType.PYTHON,
            source=ToolSource(type=ToolSourceType.Code, path=file))
        tool = tool_loader.load_tool_for_node(node, working_dir)
        assert tool.name == "sample_tool"


# This tool is for testing tools_manager.ToolLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input
