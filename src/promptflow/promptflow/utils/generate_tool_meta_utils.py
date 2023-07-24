"""
This file can generate a meta file for the given prompt template or a python file.
"""
import inspect
import json
import re
import types
from dataclasses import asdict

from jinja2.environment import COMMENT_END_STRING, COMMENT_START_STRING

from promptflow.core.tool import ToolProvider
from promptflow.contracts.tool import InputDefinition, Tool, ToolType, ValueType
from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.utils.tool_utils import function_to_interface, get_inputs_for_prompt_template


def asdict_without_none(obj):
    return asdict(obj, dict_factory=lambda x: {k: v for (k, v) in x if v})


def generate_prompt_tool(name, content, prompt_only=False, source=None):
    """Generate meta for a single jinja template file."""
    # Get all the variable name from a jinja template
    try:
        inputs = get_inputs_for_prompt_template(content)
    except Exception as e:
        msg = f"Parsing jinja got exception: {e}"
        raise JinjaParsingError(msg) from e

    import promptflow.tools  # noqa: F401
    from promptflow.core.tools_manager import reserved_keys

    for input in inputs:
        if input in reserved_keys:
            msg = f"Parsing jinja got exception: Variable name {input} is reserved by LLM. Please change another name."
            raise ReservedVariableCannotBeUsed(msg)

    pattern = f"{COMMENT_START_STRING}(((?!{COMMENT_END_STRING}).)*){COMMENT_END_STRING}"
    match_result = re.match(pattern, content)
    description = match_result.groups()[0].strip() if match_result else None
    # Construct the Tool structure
    tool = Tool(
        name=name,
        description=description,
        type=ToolType.PROMPT if prompt_only else ToolType.LLM,
        inputs={i: InputDefinition(type=[ValueType.STRING]) for i in inputs},
        outputs={},
    )
    if source is None:
        tool.code = content
    else:
        tool.source = source
    return tool


def generate_prompt_meta_dict(name, content, prompt_only=False, source=None):
    return asdict_without_none(generate_prompt_tool(name, content, prompt_only, source))


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
                    tools.append(method)
    return tools


def _parse_tool_from_function(f):
    if hasattr(f, "__tool") and isinstance(f.__tool, Tool):
        return f.__tool
    if hasattr(f, "__original_function"):
        f = f.__original_function
    try:
        inputs, _, _ = function_to_interface(f)
    except Exception as e:
        raise BadFunctionInterface(f"Failed to parse interface for tool {f.__name__}, reason: {e}") from e
    class_name = None
    if "." in f.__qualname__:
        class_name = f.__qualname__.replace(f".{f.__name__}", "")
    # Construct the Tool structure
    return Tool(
        name=f.__qualname__,
        description=inspect.getdoc(f),
        inputs=inputs,
        type=ToolType.PYTHON,
        class_name=class_name,
        function=f.__name__,
        module=f.__module__,
    )


def generate_python_tools_in_module(module):
    tool_functions = collect_tool_functions_in_module(module)
    tool_methods = collect_tool_methods_in_module(module)
    return [_parse_tool_from_function(f) for f in tool_functions + tool_methods]


def generate_python_tools_in_module_as_dict(module):
    tools = generate_python_tools_in_module(module)
    return {
        f"{t.module}.{t.name}": asdict_without_none(t) for t in tools
    }


def generate_python_tool(name, content, source=None):
    try:
        m = types.ModuleType("promptflow.dummy")
        exec(content, m.__dict__)
    except Exception as e:
        msg = f"Parsing python got exception: {e}"
        raise PythonParsingError(msg) from e
    tools = collect_tool_functions_in_module(m)
    if len(tools) == 0:
        raise NoToolDefined("No tool found in the python script.")
    elif len(tools) > 1:
        tool_names = ", ".join(t.__name__ for t in tools)
        raise MultipleToolsDefined(f"Expected 1 but collected {len(tools)} tools: {tool_names}.")
    f = tools[0]
    tool = _parse_tool_from_function(f)
    tool.module = None
    if name is not None:
        tool.name = name
    if source is None:
        tool.code = content
    else:
        tool.source = source
    return tool


def generate_python_meta_dict(name, content, source=None):
    return asdict_without_none(generate_python_tool(name, content, source))


def generate_python_meta(name, content, source=None):
    return json.dumps(generate_python_meta_dict(name, content, source), indent=2)


def generate_prompt_meta(name, content, prompt_only=False, source=None):
    return json.dumps(generate_prompt_meta_dict(name, content, prompt_only, source), indent=2)


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.TOOL)


class JinjaParsingError(ToolValidationError):
    pass


class ReservedVariableCannotBeUsed(JinjaParsingError):
    pass


class PythonParsingError(ToolValidationError):
    pass


class NoToolDefined(PythonParsingError):
    pass


class MultipleToolsDefined(PythonParsingError):
    pass


class BadFunctionInterface(PythonParsingError):
    pass
