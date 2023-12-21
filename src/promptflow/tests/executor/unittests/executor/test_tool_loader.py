from pathlib import Path

import pytest

from promptflow import tool
from promptflow._core._errors import PackageToolNotFoundError
from promptflow.contracts.flow import Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import UserErrorException
from promptflow.executor._tool_loader import ToolLoader


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
        mocker.patch("promptflow.executor._tool_loader.collect_package_tools", return_value=package_tools)
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
        mocker.patch("promptflow.executor._tool_loader.collect_package_tools", return_value=package_tools)
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


# This tool is for testing ToolLoader.load_tool_for_script_node
@tool
def sample_tool(input: str):
    return input
