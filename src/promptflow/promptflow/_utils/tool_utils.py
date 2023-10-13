# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import logging
from enum import Enum, EnumMeta
from typing import Callable, Union, get_args, get_origin

from jinja2 import Environment, meta

from ..contracts.tool import ConnectionType, InputDefinition, Tool, ValueType
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


def param_to_definition(param, should_gen_custom_type=False) -> (InputDefinition, bool):
    default_value = param.default
    # Get value type and enum from annotation
    value_type = resolve_annotation(param.annotation)
    enum = None
    custom_type = None
    # Get value type and enum from default if no annotation
    if default_value is not inspect.Parameter.empty and value_type == inspect.Parameter.empty:
        value_type = default_value.__class__ if isinstance(default_value, Enum) else type(default_value)
    # Extract enum for enum class
    if isinstance(value_type, EnumMeta):
        enum = [str(option.value) for option in value_type]
        value_type = str
    is_connection = False
    if ConnectionType.is_connection_value(value_type):
        if ConnectionType.is_custom_strong_type(value_type):
            typ = ["CustomConnection"]
            custom_type = [value_type.__name__]
        else:
            typ = [value_type.__name__]
        is_connection = True
    elif isinstance(value_type, list):
        if not all(ConnectionType.is_connection_value(t) for t in value_type):
            typ = [ValueType.OBJECT]
        else:
            custom_connection_added = False
            typ = []
            custom_type = []
            for t in value_type:
                if ConnectionType.is_custom_strong_type(t):
                    if not custom_connection_added:
                        custom_connection_added = True
                        typ.append("CustomConnection")
                    custom_type.append(t.__name__)
                else:
                    if t.__name__ == "CustomConnection":
                        custom_connection_added = True
                    typ.append(t.__name__)
            is_connection = True
    else:
        typ = [ValueType.from_type(value_type)]
    # Do not generate custom type when generating flow.tools.json for script tool.
    if not should_gen_custom_type:
        custom_type = None
    return (
        InputDefinition(
            type=typ, default=value_to_str(default_value), description=None, enum=enum, custom_type=custom_type
        ),
        is_connection,
    )


def function_to_interface(f: Callable, initialize_inputs=None, should_gen_custom_type=False) -> tuple:
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
        input_def, is_connection = param_to_definition(v, should_gen_custom_type=should_gen_custom_type)
        input_defs[k] = input_def
        if is_connection:
            connection_types.append(input_def.type)
    outputs = {}
    # Note: We don't have output definition now
    return input_defs, outputs, connection_types


def function_to_tool_definition(f: Callable, type=None, initialize_inputs=None) -> Tool:
    """Translate a function to tool definition.

    :param f: Function to be translated.
    :param type: Tool type
    :param initialize_inputs: The initialize() func inputs get by get_initialize_inputs() when function
        defined in class. We will merge those inputs with f() inputs.
    :return: The tool definition.
    """
    if hasattr(f, "__original_function"):
        f = f.__original_function
    inputs, outputs, _ = function_to_interface(f, initialize_inputs)
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
    }
    return Tool(type=type, module=f.__module__, **meta_dict, is_builtin=True, stage="test")


def get_inputs_for_prompt_template(template_str):
    """Get all input variable names from a jinja2 template string."""
    env = Environment()
    template = env.parse(template_str)
    return sorted(meta.find_undeclared_variables(template), key=lambda x: template_str.find(x))


def get_prompt_param_name_from_func(f):
    """Get the param name of prompt template on provider."""
    return next((k for k, annotation in f.__annotations__.items() if annotation == PromptTemplate), None)
