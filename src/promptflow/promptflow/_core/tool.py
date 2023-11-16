# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import importlib
import logging
from abc import ABC
from enum import Enum
from typing import Callable, Optional, List, Dict, Union, get_args, get_origin
from dataclasses import dataclass, InitVar, field

module_logger = logging.getLogger(__name__)
STREAMING_OPTION_PARAMETER_ATTR = "_streaming_option_parameter"


# copied from promptflow.contracts.tool import ToolType
class ToolType(str, Enum):
    LLM = "llm"
    PYTHON = "python"
    PROMPT = "prompt"
    _ACTION = "action"
    CUSTOM_LLM = "custom_llm"


class ToolInvoker(ABC):
    _active_tool_invoker: Optional["ToolInvoker"] = None

    def invoke_tool(self, f, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def activate(cls, tool_invoker: "ToolInvoker"):
        cls._active_tool_invoker = tool_invoker

    @classmethod
    def deactivate(cls):
        cls._active_tool_invoker = None

    @classmethod
    def active_instance(cls) -> Optional["ToolInvoker"]:
        return cls._active_tool_invoker


def tool(
    func=None,
    *,
    name: str = None,
    description: str = None,
    type: str = None,
    input_settings=None,
    streaming_option_parameter: Optional[str] = None,
    **kwargs,
) -> Callable:
    """Decorator for tool functions. The decorated function will be registered as a tool and can be used in a flow.

    :param name: The tool name.
    :type name: str
    :param description: The tool description.
    :type description: str
    :param type: The tool type.
    :type type: str
    :param input_settings: Dict of input setting.
    :type input_settings: Dict[str, promptflow.entities.InputSetting]
    :return: The decorated function.
    :rtype: Callable
    """

    def tool_decorator(func: Callable) -> Callable:
        from promptflow.exceptions import UserErrorException
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def new_f_async(*args, **kwargs):
                from .tracer import Tracer
                if Tracer.active_instance() is None:
                    return await func(*args, **kwargs)
                return await Tracer.invoke_tool_async(func, args, kwargs)
            new_f = new_f_async
        else:
            @functools.wraps(func)
            def new_f(*args, **kwargs):
                from .tracer import Tracer
                if Tracer.active_instance() is None:
                    return func(*args, **kwargs)  # Do nothing if no tracing is enabled.
                return Tracer.invoke_tool(func, args, kwargs)

        if type is not None and type not in [k.value for k in ToolType]:
            raise UserErrorException(f"Tool type {type} is not supported yet.")

        new_f.__original_function = func
        func.__wrapped_function = new_f
        new_f.__tool = None  # This will be set when generating the tool definition.
        new_f.__name = name
        new_f.__description = description
        new_f.__type = type
        new_f.__input_settings = input_settings
        new_f.__extra_info = kwargs
        if streaming_option_parameter and isinstance(streaming_option_parameter, str):
            setattr(new_f, STREAMING_OPTION_PARAMETER_ATTR, streaming_option_parameter)

        return new_f

    # enable use decorator without "()" if all arguments are default values
    if func is not None:
        return tool_decorator(func)
    return tool_decorator


def parse_all_args(argnames, args, kwargs) -> dict:
    """Parse args + kwargs to kwargs."""
    all_args = {name: value for name, value in zip(argnames, args)}
    all_args.update(kwargs)
    return all_args


class ToolProvider(ABC):
    """The base class of tool class."""

    _initialize_inputs = None
    _required_initialize_inputs = None
    _instance_init_params = None

    def __new__(cls, *args, **kwargs):
        # Record the init parameters, use __new__ so that user doesn't need to
        # repeat parameters when calling super().__init__()
        cls._instance_init_params = parse_all_args(cls.get_initialize_inputs().keys(), args, kwargs)
        return super(ToolProvider, cls).__new__(cls)

    def __init__(self):
        """
        Define the base inputs of each tool.
        All the parameters of __init__ will be added to inputs of each @tool in the class.
        """
        self._init_params = self._instance_init_params

    @classmethod
    def get_initialize_inputs(cls):
        if not cls._initialize_inputs:
            cls._initialize_inputs = {
                k: v for k, v in inspect.signature(cls.__init__).parameters.items() if k != "self"
            }
        return cls._initialize_inputs

    @classmethod
    def get_required_initialize_inputs(cls):
        if not cls._required_initialize_inputs:
            cls._required_initialize_inputs = {
                k: v
                for k, v in inspect.signature(cls.__init__).parameters.items()
                if k != "self" and v.default is inspect.Parameter.empty
            }
        return cls._required_initialize_inputs


@dataclass
class DynamicList:

    function: InitVar[Union[str, Callable]]
    """The dynamic list function."""

    input_mapping: InitVar[Dict] = None
    """The mapping between dynamic list function inputs and tool inputs."""

    func_path: str = field(init=False)
    func_kwargs: List = field(init=False)

    def __post_init__(self, function, input_mapping):
        from promptflow.exceptions import UserErrorException
        from promptflow.contracts.tool import ValueType

        # Validate function exist
        if isinstance(function, str):
            func = importlib.import_module(tool["module"])
            func_path = function
        elif isinstance(function, Callable):
            func = function
            func_path = f"{function.__module__}.{function.__name__}"
        else:
            raise UserErrorException(
                "Function has invalid type, please provide callable or function name for function.")
        self.func_path = func_path
        self._func_obj = func
        self._input_mapping = input_mapping or {}

        # Get function input info
        self.func_kwargs = []
        inputs = inspect.signature(self._func_obj).parameters
        for name, value in inputs.items():
            if value.kind != value.VAR_KEYWORD and value.kind != value.VAR_POSITIONAL:
                input_info = {"name": name}
                if value.annotation is not inspect.Parameter.empty:
                    if get_origin(value.annotation):
                        input_info["type"] = [annotation.__name__ for annotation in get_args(value.annotation)]
                    else:
                        input_info["type"] = [ValueType.from_type(value.annotation)]
                if name in self._input_mapping:
                    input_info["reference"] = f"${{inputs.{self._input_mapping[name]}}}"
                input_info["optional"] = value.default is not inspect.Parameter.empty
                if input_info["optional"]:
                    input_info["default"] = value.default
                self.func_kwargs.append(input_info)


@dataclass
class InputSetting:
    """Settings of the tool input"""

    is_multi_select: bool = None
    """Allow user to select multiple values."""

    allow_manual_entry: bool = None
    """Allow user to enter input value manually."""

    enabled_by: str = None
    """The input field which must be an enum type, that controls the visibility of the dependent input field."""

    enabled_by_value: List = None
    """Defines the accepted enum values from the enabled_by field that will make this dependent input field visible."""

    dynamic_list: DynamicList = None
    """Settings of dynamic list function."""
