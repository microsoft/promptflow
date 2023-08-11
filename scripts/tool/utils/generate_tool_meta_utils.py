"""
This file can generate a meta file for the given prompt template or a python file.
"""
import inspect
import types
from dataclasses import asdict

from utils.tool_utils import function_to_interface

from promptflow.contracts.tool import Tool, ToolType
from promptflow.core.tool import ToolProvider
from promptflow.exceptions import ErrorTarget, UserErrorException


def asdict_without_none(obj):
    return asdict(obj, dict_factory=lambda x: {k: v for (k, v) in x if v})


def is_tool(f):
    if not isinstance(f, types.FunctionType):
        return False
    if not hasattr(f, "__tool"):
        return False
    return True


def collect_tool_functions_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if is_tool(obj):
            # Note that the tool should be in defined in exec but not imported in exec,
            # so it should also have the same module with the current function.
            if getattr(obj, "__module__", "") != m.__name__:
                continue
            tools.append(obj)
    return tools


def collect_tool_methods_in_module(m):
    tools = []
    for _, obj in inspect.getmembers(m):
        if isinstance(obj, type) and issubclass(obj, ToolProvider) and obj.__module__ == m.__name__:
            for _, method in inspect.getmembers(obj):
                if is_tool(method):
                    initialize_inputs = obj.get_initialize_inputs()
                    tools.append((method, initialize_inputs))
    return tools


def _parse_tool_from_function(f, initialize_inputs=None, tool_type=ToolType.PYTHON, name=None, description=None):
    if hasattr(f, "__tool") and isinstance(f.__tool, Tool):
        return f.__tool
    if hasattr(f, "__original_function"):
        f = f.__original_function
    try:
        inputs, _, _ = function_to_interface(f, tool_type=tool_type, initialize_inputs=initialize_inputs)
    except Exception as e:
        raise BadFunctionInterface(f"Failed to parse interface for tool {f.__name__}, reason: {e}") from e
    class_name = None
    if "." in f.__qualname__:
        class_name = f.__qualname__.replace(f".{f.__name__}", "")
    # Construct the Tool structure
    return Tool(
        name=name or f.__qualname__,
        description=description or inspect.getdoc(f),
        inputs=inputs,
        type=tool_type,
        class_name=class_name,
        function=f.__name__,
        module=f.__module__,
    )


def generate_python_tools_in_module(module, name, description):
    tool_functions = collect_tool_functions_in_module(module)
    tool_methods = collect_tool_methods_in_module(module)
    return [_parse_tool_from_function(f, name=name, description=description) for f in tool_functions] + [
        _parse_tool_from_function(f, initialize_inputs, name=name, description=description)
        for (f, initialize_inputs) in tool_methods
    ]


def generate_python_tools_in_module_as_dict(module, name=None, description=None):
    tools = generate_python_tools_in_module(module, name, description)
    return {f"{t.module}.{t.name}": asdict_without_none(t) for t in tools}


def generate_custom_llm_tools_in_module(module, name, description):
    tool_functions = collect_tool_functions_in_module(module)
    tool_methods = collect_tool_methods_in_module(module)
    return [
        _parse_tool_from_function(f, tool_type=ToolType.CUSTOM_LLM, name=name, description=description)
        for f in tool_functions
    ] + [
        _parse_tool_from_function(
            f, initialize_inputs, tool_type=ToolType.CUSTOM_LLM, name=name, description=description
        )
        for (f, initialize_inputs) in tool_methods
    ]


def generate_custom_llm_tools_in_module_as_dict(module, name=None, description=None):
    tools = generate_custom_llm_tools_in_module(module, name, description)
    return {f"{t.module}.{t.name}": asdict_without_none(t) for t in tools}


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.TOOL)


class PythonParsingError(ToolValidationError):
    pass


class BadFunctionInterface(PythonParsingError):
    pass
