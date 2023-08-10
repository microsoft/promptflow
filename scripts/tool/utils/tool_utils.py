import inspect
from enum import Enum, EnumMeta
from typing import Callable, Union, get_args, get_origin
from promptflow.contracts.tool import ConnectionType, InputDefinition, ValueType, ToolType
from promptflow.contracts.types import PromptTemplate


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


def param_to_definition(param, value_type) -> (InputDefinition, bool):
    default_value = param.default
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


def function_to_interface(f: Callable, tool_type, initialize_inputs=None) -> tuple:
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
        # Get value type from annotation
        value_type = resolve_annotation(v.annotation)
        if tool_type==ToolType.CUSTOM_LLM and value_type is PromptTemplate:
            # custom llm tool has prompt template as input, skip it
            continue
        input_def, is_connection = param_to_definition(v, value_type)
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

