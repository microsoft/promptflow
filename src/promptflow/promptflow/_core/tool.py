# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import json
import logging
from abc import ABC
from dataclasses import asdict
from enum import Enum
from typing import Optional

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


def tool(f):
    @functools.wraps(f)
    def new_f(*args, **kwargs):
        tool_invoker = ToolInvoker.active_instance()
        # If there is no active tool invoker for tracing or other purposes, just call the function.
        if tool_invoker is None:
            return f(*args, **kwargs)
        return tool_invoker.invoke_tool(f, *args, **kwargs)

    new_f.__original_function = f
    f.__wrapped_function = new_f
    new_f.__tool = None  # This will be set when generating the tool definition.
    return new_f


def parse_all_args(argnames, args, kwargs) -> dict:
    """Parse args + kwargs to kwargs."""
    all_args = {name: value for name, value in zip(argnames, args)}
    all_args.update(kwargs)
    return all_args


def dump(func, name=None, description=None):
    try:
        if not func.__tool:
            from promptflow._utils.tool_utils import function_to_tool_definition

            func.__tool = function_to_tool_definition(func, type=ToolType.PYTHON)
        if name:
            func.__tool.name = name
        if description:
            func.__tool.description = description
        data = asdict(
            func.__tool,
            dict_factory=lambda x: {
                k: v for (k, v) in x if v is not None and k != "outputs"
            },
        )
        return json.dumps(data, indent=2)
    except Exception as e:
        raise Exception("Dump tool failed. ") from e


class ToolProvider(ABC):
    """The base class of tool class."""

    _initialize_inputs = None
    _required_initialize_inputs = None
    _instance_init_params = None

    def __new__(cls, *args, **kwargs):
        # Record the init parameters, use __new__ so that user doesn't need to
        # repeat parameters when calling super().__init__()
        cls._instance_init_params = parse_all_args(
            cls.get_initialize_inputs().keys(), args, kwargs
        )
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
                k: v
                for k, v in inspect.signature(cls.__init__).parameters.items()
                if k != "self"
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
