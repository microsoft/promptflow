import logging
import types
from typing import List, Dict, Optional, Tuple

from promptflow._core._errors import PackageToolNotFoundError
from promptflow._core.tool_meta_generator import (
    _parse_tool_from_function,
    collect_tool_function_in_module,
    load_python_module_from_file,
)
from promptflow._core.tools_manager import collect_package_tools, BuiltinsManager
from promptflow._utils.tool_utils import _find_deprecated_tools
from promptflow.contracts.flow import Node, Tool, ToolType, ToolSourceType
from promptflow.executor._errors import UserErrorException, SystemErrorException
from promptflow.exceptions import ErrorTarget

module_logger = logging.getLogger(__name__)


class ToolLoader:
    def __init__(self, working_dir: str, package_tool_keys: Optional[List[str]] = None) -> None:
        self._working_dir = working_dir
        self._package_tools = collect_package_tools(package_tool_keys) if package_tool_keys else {}
        # Used to handle backward compatibility of tool ID changes.
        self._deprecated_tools = _find_deprecated_tools(self._package_tools)
        self._loaded_tools = {}

    @property
    def loaded_tools(self) -> Dict[str, Tool]:
        return self._loaded_tools

    # TODO: Replace NotImplementedError with NotSupported in the future.
    def load_tool_for_node(self, node: Node) -> Tool:
        if node.source is None:
            raise UserErrorException(f"Node {node.name} does not have source defined.")
        if node.type == ToolType.PYTHON:
            if node.source.type == ToolSourceType.Package:
                return self.load_tool_for_package_node(node)
            elif node.source.type == ToolSourceType.Code:
                _, tool = self.load_tool_for_script_node(node)
                return tool
            raise NotImplementedError(f"Tool source type {node.source.type} for python tool is not supported yet.")
        elif node.type == ToolType.CUSTOM_LLM:
            if node.source.type == ToolSourceType.PackageWithPrompt:
                return self.load_tool_for_package_node(node)
            raise NotImplementedError(f"Tool source type {node.source.type} for custom_llm tool is not supported yet.")
        else:
            raise NotImplementedError(f"Tool type {node.type} is not supported yet.")

    def load_tool_for_package_node(self, node: Node) -> Tool:
        if node.name in self._loaded_tools:
            return self._loaded_tools[node.name]

        if node.source.tool in self._package_tools:
            return Tool.deserialize(self._package_tools[node.source.tool])

        # If node source tool is not in package tools, try to find the tool ID in deprecated tools.
        # If found, load the tool with the new tool ID for backward compatibility.
        if node.source.tool in self._deprecated_tools:
            new_tool_id = self._deprecated_tools[node.source.tool]
            # Used to collect deprecated tool usage and warn user to replace the deprecated tool with the new one.
            module_logger.warning(f"Tool ID '{node.source.tool}' is deprecated. Please use '{new_tool_id}' instead.")
            tool = Tool.deserialize(self._package_tools[new_tool_id])
            self._loaded_tools[node.name] = tool

        raise PackageToolNotFoundError(
            f"Package tool '{node.source.tool}' is not found in the current environment. "
            f"All available package tools are: {list(self._package_tools.keys())}.",
            target=ErrorTarget.EXECUTOR,
        )

    def load_tool_for_script_node(self, node: Node) -> Tuple[types.ModuleType, Tool]:
        if node.name in self._loaded_tools:
            return self._loaded_tools[node.name]

        if node.source.path is None:
            raise UserErrorException(f"Node {node.name} does not have source path defined.")
        path = node.source.path
        m = load_python_module_from_file(self._working_dir / path)
        if m is None:
            raise CustomToolSourceLoadError(f"Cannot load module from {path}.")
        f, init_inputs = collect_tool_function_in_module(m)
        tool = _parse_tool_from_function(f, init_inputs, gen_custom_type_conn=True)
        self._loaded_tools[node.name] = (m, tool)
        return m, tool

    def load_tool_for_llm_node(self, node: Node) -> Tool:
        if node.name in self._loaded_tools:
            return self._loaded_tools[node.name]

        api_name = f"{node.provider}.{node.api}"
        tool = BuiltinsManager._load_llm_api(api_name)
        self._loaded_tools[node.name] = tool
        return tool


class CustomToolSourceLoadError(SystemErrorException):
    pass
