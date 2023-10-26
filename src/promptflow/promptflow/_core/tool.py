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


# copied from promptflow.contracts.tool import ToolType
class ToolType(str, Enum):
    LLM = "llm"
    PYTHON = "python"
    PROMPT = "prompt"
    _ACTION = "action"


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
    input_settings = None,
    **kwargs,
) -> Callable:
    """Decorator for tool functions. The decorated function will be registered as a tool and can be used in a flow.

    :param name: The tool name.
    :type name: str
    :param description: The tool description.
    :type description: str
    :param type: The tool type.
    :type type: str
    :param type: Input setting.
    :type type: promptflow.InputSettings
    :return: The decorated function.
    :rtype: Callable
    """

    def tool_decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def new_f(*args, **kwargs):
            tool_invoker = ToolInvoker.active_instance()
            # If there is no active tool invoker for tracing or other purposes, just call the function.
            if tool_invoker is None:
                return func(*args, **kwargs)
            return tool_invoker.invoke_tool(func, *args, **kwargs)

        new_f.__original_function = func
        func.__wrapped_function = new_f
        new_f.__tool = None  # This will be set when generating the tool definition.
        new_f.__name = name
        new_f.__description = description
        new_f.__type = type
        new_f.__input_settings = input_settings
        new_f.__extra_info = kwargs
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
    function: Union[str, Callable]
    func_kwargs: List = field(init=False)
    input_mapping: InitVar[Dict] = None

    def __post_init__(self, input_mapping):
        from promptflow.exceptions import UserErrorException

        # Validate function exist
        if isinstance(self.function, str):
            func = importlib.import_module(tool["module"])
            func_name = self.function
        elif isinstance(self.function, Callable):
            func = self.function
            func_name = f"{self.function.__module__}.{self.function.__name__}"
        else:
            raise UserErrorException(
                "Function has invalid type, please provide callable or function name for function.")
        self.function = func_name
        self._func_obj = func

        # Get function input info
        self.func_kwargs = []
        inputs = inspect.signature(self._func_obj).parameters
        for name, value in inputs.items():
            if value.kind != value.VAR_KEYWORD and value.kind != value.VAR_POSITIONAL:
                input_info = {"name": name}
                if not value.annotation is inspect.Parameter.empty:
                    # TODO type mapping
                    if get_origin(value.annotation):
                        input_info["type"] = [annotation.__name__ for annotation in get_args(value.annotation)]
                    else:
                        input_info["type"] = [value.annotation.__name__]
                if name in input_mapping:
                    input_info["reference"] = f"${{inputs.{input_mapping[name]}}}"
                input_info["optional"] = value.default is not inspect.Parameter.empty
                if input_info["optional"]:
                    input_info["default"] = value.default
                input_info["type"] = []
                self.func_kwargs.append(input_info)


@dataclass
class InputSettings:
    is_multi_select: bool = None
    allow_manual_entry: bool = None
    enabled_by: str = None
    enabled_by_value: List = None
    dynamic_list: DynamicList = None
