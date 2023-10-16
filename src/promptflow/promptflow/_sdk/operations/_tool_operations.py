# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import json
from dataclasses import asdict

from promptflow._core.tool_meta_generator import is_tool
from promptflow._utils.tool_utils import function_to_interface
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import UserErrorException
from promptflow._core.tools_manager import collect_package_tools_and_connections


class ToolOperations:
    """ToolOperations."""

    def generate_tool_meta(self, tool_module):
        tool_functions = self._collect_tool_functions_in_module(tool_module)
        tool_methods = self._collect_tool_class_methods_in_module(tool_module)
        tools = [self._parse_tool_from_function(f) for f in tool_functions] + [
            self._parse_tool_from_function(f, initialize_inputs) for (f, initialize_inputs) in tool_methods
        ]
        construct_tools = {
            f"{t.module}.{t.class_name}.{t.function}"
            if t.class_name is not None
            else f"{t.module}.{t.function}": asdict(t, dict_factory=lambda x: {k: v for (k, v) in x if v})
            for t in tools
        }
        # The generated dict cannot be dumped as yaml directly since yaml cannot handle string enum.
        return json.loads(json.dumps(construct_tools))

    @staticmethod
    def _collect_tool_functions_in_module(tool_module):
        tools = []
        for _, obj in inspect.getmembers(tool_module):
            if is_tool(obj):
                # Note that the tool should be in defined in exec but not imported in exec,
                # so it should also have the same module with the current function.
                if getattr(obj, "__module__", "") != tool_module.__name__:
                    continue
                tools.append(obj)
        return tools

    @staticmethod
    def _collect_tool_class_methods_in_module(tool_module):
        from promptflow import ToolProvider

        tools = []
        for _, obj in inspect.getmembers(tool_module):
            if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == tool_module.__name__:
                for _, method in inspect.getmembers(obj):
                    if is_tool(method):
                        initialize_inputs = obj.get_initialize_inputs()
                        tools.append((method, initialize_inputs))
        return tools

    @staticmethod
    def _parse_tool_from_function(f, initialize_inputs=None):
        tool_type = getattr(f, "__type") or ToolType.PYTHON
        tool_name = getattr(f, "__name")
        description = getattr(f, "__description")
        if getattr(f, "__tool", None) and isinstance(f.__tool, Tool):
            return getattr(f, "__tool")
        if hasattr(f, "__original_function"):
            f = getattr(f, "__original_function")
        try:
            inputs, _, _ = function_to_interface(f, initialize_inputs=initialize_inputs)
        except Exception as e:
            raise UserErrorException(f"Failed to parse interface for tool {f.__name__}, reason: {e}") from e
        class_name = None
        if "." in f.__qualname__:
            class_name = f.__qualname__.replace(f".{f.__name__}", "")
        # Construct the Tool structure
        return Tool(
            name=tool_name or f.__qualname__,
            description=description or inspect.getdoc(f),
            inputs=inputs,
            type=tool_type,
            class_name=class_name,
            function=f.__name__,
            module=f.__module__,
        )

    @staticmethod
    def list():
        # List all package to in the environment
        tools, _, _ = collect_package_tools_and_connections()
        return tools
