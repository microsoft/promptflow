# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import logging
from abc import ABC
from dataclasses import InitVar, asdict, dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Union

from promptflow.tracing._trace import _traced
from promptflow.tracing.contracts.trace import TraceType

module_logger = logging.getLogger(__name__)
STREAMING_OPTION_PARAMETER_ATTR = "_streaming_option_parameter"


# copied from promptflow.contracts.tool import ToolType
class ToolType(str, Enum):
    LLM = "llm"
    PYTHON = "python"
    CSHARP = "csharp"
    PROMPT = "prompt"
    _ACTION = "action"
    CUSTOM_LLM = "custom_llm"


# Set a node input _inputs_to_escape for llm/custom_llm/prompt tool to store flow inputs list,
# in order to enable tools to identify these inputs,
# and apply escape/unescape to avoid parsing of role in user inputs.
INPUTS_TO_ESCAPE_PARAM_KEY = "_inputs_to_escape"
TOOL_TYPE_TO_ESCAPE = [ToolType.LLM, ToolType.CUSTOM_LLM, ToolType.PROMPT]


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

        if type is not None and type not in [k.value for k in ToolType]:
            raise UserErrorException(f"Tool type {type} is not supported yet.")

        # Calls to tool functions should be traced automatically.
        new_f = _traced(func, trace_type=TraceType.FUNCTION)

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
        from promptflow._constants import SKIP_FUNC_PARAMS
        from promptflow._utils.tool_utils import _get_function_path, function_to_interface

        self._func_obj, self.func_path = _get_function_path(function)
        self._input_mapping = input_mapping or {}
        dynamic_list_func_inputs, _, _, _ = function_to_interface(
            self._func_obj, gen_custom_type_conn=True, skip_prompt_template=True
        )

        # Get function input info
        self.func_kwargs = []
        inputs = inspect.signature(self._func_obj).parameters
        for name, value in dynamic_list_func_inputs.items():
            if name not in SKIP_FUNC_PARAMS:
                input_info = {"name": name}
                input_info.update(asdict(value, dict_factory=lambda x: {k: v for (k, v) in x if v}))
                if name in self._input_mapping:
                    input_info["reference"] = f"${{inputs.{self._input_mapping[name]}}}"
                input_info["optional"] = inputs[name].default is not inspect.Parameter.empty
                if input_info["optional"]:
                    input_info["default"] = inputs[name].default
                self.func_kwargs.append(input_info)


@dataclass
class GeneratedBy:
    """Settings of the generated by"""

    function: InitVar[Union[str, Callable]]
    """The generated by function."""

    reverse_function: InitVar[Union[str, Callable]]
    """The reverse generated by function."""

    input_settings: InitVar[Dict[str, object]] = None
    """The input settings of generated by function."""

    func_path: str = field(init=False)
    func_kwargs: List = field(init=False)
    reverse_func_path: str = field(init=False)

    def __post_init__(self, function, reverse_function, input_settings):
        from promptflow._constants import SKIP_FUNC_PARAMS, UIONLY_HIDDEN
        from promptflow._utils.tool_utils import _get_function_path, function_to_interface

        self._func_obj, self.func_path = _get_function_path(function=function)
        self._reverse_func_obj, self.reverse_func_path = _get_function_path(function=reverse_function)
        self._input_settings = {}

        generated_func_inputs, _, _, _ = function_to_interface(
            self._func_obj, gen_custom_type_conn=True, skip_prompt_template=True
        )

        # Get function input info
        self.func_kwargs = []
        func_inputs = inspect.signature(self._func_obj).parameters
        for name, value in generated_func_inputs.items():
            if name not in SKIP_FUNC_PARAMS:
                # Update kwargs in generated_by settings
                input_info = {"name": name}
                input_info.update(asdict(value, dict_factory=lambda x: {k: v for (k, v) in x if v}))
                input_info["reference"] = f"${{inputs.{name}}}"
                input_info["optional"] = func_inputs[name].default is not inspect.Parameter.empty
                self.func_kwargs.append(input_info)

                # Generated generated_by input settings in tool func
                if name in input_settings:
                    self._input_settings[name] = asdict(
                        input_settings[name], dict_factory=lambda x: {k: v for (k, v) in x if v}
                    )
                    if "type" in input_info:
                        self._input_settings[name]["type"] = input_info["type"]
                    self._input_settings[name]["input_type"] = UIONLY_HIDDEN


@dataclass(init=False)
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

    generated_by: GeneratedBy = None
    """Settings of generated by function."""

    def __init__(self, **kwargs):
        self.is_multi_select = kwargs.pop("is_multi_select", None)
        self.allow_manual_entry = kwargs.pop("allow_manual_entry", None)
        self.enabled_by = kwargs.pop("enabled_by", None)
        self.enabled_by_value = kwargs.pop("enabled_by_value", None)
        self.dynamic_list = kwargs.pop("dynamic_list", None)
        self.generated_by = kwargs.pop("generated_by", None)
        self._kwargs = kwargs
