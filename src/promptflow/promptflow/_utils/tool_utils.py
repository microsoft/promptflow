# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import logging
import re
import uuid
from dataclasses import is_dataclass
from enum import Enum, EnumMeta
from typing import Callable, Union, get_args, get_origin

from jinja2 import Environment, meta

from .._utils.ast_parser import AstParser
from ..contracts.tool import ConnectionType, InputDefinition, Tool, ToolType, ValueType
from ..contracts.types import PromptTemplate

module_logger = logging.getLogger(__name__)


def value_to_str(val):
    if val is inspect.Parameter.empty:
        # For empty case, default field will be skipped when dumping to json
        return None
    if val is None:
        # Dump default: "" in json to avoid UI validation error
        return ""
    if isinstance(val, Enum):
        return val.value
    return str(val)


def resolve_annotation(anno) -> Union[str, list]:
    """Resolve the union annotation to type list."""
    origin = get_origin(anno)
    if origin != Union:
        return anno
    # Optional[Type] is Union[Type, NoneType], filter NoneType out
    args = [arg for arg in get_args(anno) if arg != type(None)]  # noqa: E721
    return args[0] if len(args) == 1 else args


def param_to_definition(param) -> (InputDefinition, bool):
    default_value = param.default
    # Get value type and enum from annotation
    value_type = resolve_annotation(param.annotation)
    enum = None
    # Get value type and enum from default if no annotation
    if default_value is not inspect.Parameter.empty and value_type == inspect.Parameter.empty:
        value_type = default_value.__class__ if isinstance(default_value, Enum) else type(default_value)
    # Extract enum for enum class
    if isinstance(value_type, EnumMeta):
        enum = [str(option.value) for option in value_type]
        value_type = str
    is_connection = False
    if ConnectionType.is_connection_value(value_type):
        typ = [value_type.__name__]
        is_connection = True
    elif isinstance(value_type, list):
        if not all(ConnectionType.is_connection_value(t) for t in value_type):
            typ = [ValueType.OBJECT]
        else:
            typ = [t.__name__ for t in value_type]
            is_connection = True
    else:
        typ = [ValueType.from_type(value_type)]
    return InputDefinition(type=typ, default=value_to_str(default_value), description=None, enum=enum), is_connection


def function_to_interface(f: Callable, initialize_inputs=None) -> tuple:
    sign = inspect.signature(f)
    all_inputs = {}
    input_defs = {}
    connection_types = []
    # Collect all inputs from class and func
    if initialize_inputs:
        if any(k for k in initialize_inputs if k in sign.parameters):
            raise Exception(f'Duplicate inputs found from {f.__name__!r} and "__init__()"!')
        all_inputs = {**initialize_inputs}
    all_inputs.update(
        {
            k: v
            for k, v in sign.parameters.items()
            if k != "self" and v.kind != v.VAR_KEYWORD and v.kind != v.VAR_POSITIONAL  # TODO: Handle these cases
        }
    )
    # Resolve inputs to definitions.
    for k, v in all_inputs.items():
        input_def, is_connection = param_to_definition(v)
        input_defs[k] = input_def
        if is_connection:
            connection_types.append(input_def.type)
    outputs = {}
    # Note: We don't have output definition now
    # outputs = {"output": OutputDefinition("output", [ValueType.from_type(type(sign.return_annotation))], "", True)}
    # if is_dataclass(sign.return_annotation):
    #     for f in fields(sign.return_annotation):
    #         outputs[f.name] = OutputDefinition(f.name, [ValueType.from_type(
    #             type(getattr(sign.return_annotation, f.name)))], "", False)
    return input_defs, outputs, connection_types


def referenced_global_variable_names(f: Callable):
    """Get global variable names that are referenced in the given function."""

    yield from f.__code__.co_names

    # f.__code__.co_names does not contain the variable names that are used in parameter defaults,
    # we need to lookup them from the function definition using AST.
    ast_parser = AstParser(inspect.getsource(f))
    function_analyzer = ast_parser.get_function(f.__name__)
    yield from function_analyzer.get_referenced_variable_names_in_parameter_defaults()


def parse_globals(f: Callable):
    f = getattr(f, "__original_function", f)
    required_globals = {name: f.__globals__.get(name) for name in referenced_global_variable_names(f)}
    # Types on function annotation also need to be included.
    required_globals.update(
        {v.__name__: f.__globals__.get(v.__name__) for v in f.__annotations__.values() if isinstance(v, type)}
    )
    required_globals = {name: value for name, value in required_globals.items() if value is not None}
    return required_globals


def prepare_global_variable(name, value):
    if isinstance(value, str):
        return f'{name} = """{value}"""'
    if isinstance(value, (int, float)):
        return f"{name} = {value}"
    return None


def prepare_dataclass_code(name, value):
    if not is_dataclass(value):
        return None
    return "from dataclasses import dataclass\n@dataclass\n" + inspect.getsource(value)


def prepare_builtin_module(name, value):
    if not inspect.ismodule(value):
        return None

    module_name = value.__name__
    suffix = f" as {name}" if name != module_name else ""

    if value.__package__ and value.__package__ != module_name:
        package_prefix = ".".join(value.__package__.split(".")[:-1])
        return f"from {package_prefix} import {module_name}{suffix}"
    return f"import {module_name}{suffix}"


def prepare_builtin_connection(name, value):
    # Handle connection dataclass
    from promptflow._core.tools_manager import connections

    connection_name = next((k for k, v in connections.items() if v is value), None)
    if connection_name:
        import_str = f"from promptflow.connections import {connection_name}"
        if connection_name != name:
            import_str += f" as {name}"
        return f"{import_str}"
    return None


def prepare_builtin_tool_imports(name, value):
    if not hasattr(value, "__module__"):
        return None

    module_name = value.__name__
    suffix = f" as {name}" if name != module_name else ""
    return f"from {value.__module__} import {module_name}{suffix}"


prepare_functions = (
    prepare_builtin_module,
    prepare_builtin_connection,
    prepare_builtin_tool_imports,
    prepare_global_variable,
    prepare_dataclass_code,
)

PROMPTFLOW_GLOBALS = {"tool", "log_metric", "log_node_metric", "log_flow_metric"}


def prepare_globals(function_globals):
    sources = [
        "from typing import List, Mapping, Dict",
    ]
    promptflow_globals = sorted([name for name in function_globals.keys() if name in PROMPTFLOW_GLOBALS])
    if "tool" not in function_globals:
        promptflow_globals = ["tool"] + promptflow_globals
    sources.append(f"from promptflow import {', '.join(promptflow_globals)}")
    for name, value in function_globals.items():
        if name in PROMPTFLOW_GLOBALS:
            continue
        source = None
        for f in prepare_functions:
            source_f = f(name, value)
            if source_f is not None:
                source = source_f
                break
        if source is None:
            log = f"Unable to prepare globals for variable {name} with value {value}, type={type(value)}"
            module_logger.warning(log)
            sources.append("#  " + log)
        else:
            sources.append(source)
    return "\n".join(sources)


def prepare_file_code(existing_globals):
    sources = []
    for name, item in existing_globals.items():
        try:
            sources.append(inspect.getsource(item))
        except Exception:
            log = f"Unable to get source for function {name} with value {item}."
            module_logger.warning(log)
            sources.append("#  " + log)

    return "\n\n".join(sources)


def create_function_source(f, existing_globals={}) -> str:
    """This function will collect globals which execute f requires and add them to code."""
    existing_globals = existing_globals or {}
    function_globals = parse_globals(f)
    # TODO: Handle them for more scenarios
    # Filter out function in same file with f
    file_scoped_functions = {
        k: v for k, v in function_globals.items() if isinstance(v, Callable) and v.__module__ == f.__module__
    }
    function_globals = {
        k: v for k, v in function_globals.items() if k not in existing_globals and k not in file_scoped_functions
    }
    function_source = inspect.getsource(f)
    function_prefix = prepare_globals(function_globals)
    file_code_source = prepare_file_code(file_scoped_functions)
    file_code_source = f"\n\n{file_code_source}" if file_code_source else ""
    return f"{function_prefix}{file_code_source}\n\n{function_source}"


def function_to_tool_definition(
    f: Callable, type=None, is_builtin=False, provided_kwargs=None, prompt_name_mapping=None, initialize_inputs=None
) -> Tool:
    """Translate a function to tool definition.

    :param f: Function to be translated.
    :param type: Tool type, if not provided, default to custom script tool.
    :param is_builtin: Is builtin tool or not. 'code' will not generated if is_builtin.
    :param provided_kwargs: Required when type is PROMPT. Provided kwargs when
        calling the function, to get the prompt template string.
    :param prompt_name_mapping: The prompt value to variable name recorded from globals when
        executing, will be used as prompt tool name if exists.
    :param initialize_inputs: The initialize() func inputs get by get_initialize_inputs() when function
        defined in class. We will merge those inputs with f() inputs.
    :return: The tool definition.
    """
    if hasattr(f, "__original_function"):
        f = f.__original_function
    inputs, outputs, connection_types = function_to_interface(f, initialize_inputs)
    # Hack to get class name
    class_name = None
    if "." in f.__qualname__:
        class_name = f.__qualname__.replace(f".{f.__name__}", "")
    meta_dict = {
        "name": f.__qualname__,
        "description": inspect.getdoc(f) or None,
        "inputs": inputs,
        "outputs": outputs,
        "class_name": class_name,
        "function": f.__name__,
        # !!!Note: We use class name - Connection suffix as connection type, the value will be shown on UI.
        "connection_type": [re.sub("Connection$", "", i) for i in connection_types] if type is ToolType.LLM else None,
    }
    if is_builtin:
        return Tool(type=type, module=f.__module__, **meta_dict, is_builtin=True, stage="test")
    if type is ToolType.LLM:
        prompt_tpl_name = get_prompt_param_name_from_func(f)
        prompt_tpl_value = provided_kwargs.get(prompt_tpl_name, "")
        # Get prompt variable name and set as prompt tool name
        if prompt_name_mapping and prompt_tpl_value in prompt_name_mapping:
            tool_name = prompt_name_mapping[prompt_tpl_value]
        else:
            tool_name = f"prompt_{str(uuid.uuid4())[:5]}"
        inputs = get_inputs_for_prompt_template(prompt_tpl_value)
        return Tool(
            name=tool_name,
            type=ToolType.LLM,
            description="This is a llm tool",
            inputs={name: InputDefinition(type=[ValueType.STRING]) for name in inputs},
            outputs={},
            code=prompt_tpl_value,
        )
    return Tool(type=ToolType.PYTHON, code=create_function_source(f), **meta_dict)


def get_inputs_for_prompt_template(template_str):
    """Get all input variable names from a jinja2 template string."""
    env = Environment()
    template = env.parse(template_str)
    return sorted(meta.find_undeclared_variables(template), key=lambda x: template_str.find(x))


def get_prompt_param_name_from_func(f):
    """Get the param name of prompt template on provider."""
    return next((k for k, annotation in f.__annotations__.items() if annotation == PromptTemplate), None)
