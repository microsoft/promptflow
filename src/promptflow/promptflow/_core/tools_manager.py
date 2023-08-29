# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib
import importlib.util
import logging
import traceback
from functools import partial
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Tuple, Union

import pkg_resources
import yaml

from promptflow._core._errors import MissingRequiredInputs, PackageToolNotFoundError
from promptflow._core.tool_meta_generator import (
    _parse_tool_from_function,
    collect_tool_function_in_module,
    load_python_module_from_file,
)
from promptflow._utils.tool_utils import function_to_tool_definition, get_prompt_param_name_from_func
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSourceType
from promptflow.contracts.tool import Tool, ToolType
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException

module_logger = logging.getLogger(__name__)
PACKAGE_TOOLS_ENTRY = "package_tools"


def collect_tools_from_directory(base_dir) -> dict:
    tools = {}
    for f in Path(base_dir).glob("**/*.yaml"):
        with open(f, "r") as f:
            tools_in_file = yaml.safe_load(f)
            for identifier, tool in tools_in_file.items():
                tools[identifier] = tool
    return tools


def collect_package_tools(keys: Optional[List[str]] = None) -> dict:
    """Collect all tools from all installed packages."""
    all_package_tools = {}
    if keys is not None:
        keys = set(keys)
    for entry_point in pkg_resources.iter_entry_points(group=PACKAGE_TOOLS_ENTRY):
        try:
            list_tool_func = entry_point.resolve()
            package_tools = list_tool_func()
            for identifier, tool in package_tools.items():
                #  Only load required tools to avoid unnecessary loading when keys is provided
                if isinstance(keys, set) and identifier not in keys:
                    continue
                m = tool["module"]
                importlib.import_module(m)  # Import the module to make sure it is valid
                tool["package"] = entry_point.dist.project_name
                tool["package_version"] = entry_point.dist.version
                all_package_tools[identifier] = tool
        except Exception as e:
            msg = (
                f"Failed to load tools from package {entry_point.dist.project_name}: {e},"
                + f" traceback: {traceback.format_exc()}"
            )
            module_logger.warning(msg)
    return all_package_tools


class BuiltinsManager:
    def __init__(self) -> None:
        pass

    @staticmethod
    def _load_llm_api(api_name: str) -> Tool:
        result = apis.get(api_name)
        if result is None:
            raise APINotFound(
                message=f"The API '{api_name}' is not found.",
                target=ErrorTarget.EXECUTOR,
            )
        return result

    def load_builtin(
        self,
        tool: Tool,
        node_inputs: Optional[dict] = None,
    ) -> Tuple[Callable, dict]:
        return BuiltinsManager._load_package_tool(tool.name, tool.module, tool.class_name, tool.function, node_inputs)

    @staticmethod
    def _load_package_tool(tool_name, module_name, class_name, method_name, node_inputs: Mapping[str, InputAssignment]):
        """Load package in tool with given import path and node inputs."""
        m = importlib.import_module(module_name)
        if class_name is None:
            return getattr(m, method_name), {}
        provider_class = getattr(m, class_name)
        # Note: v -- type is InputAssignment
        init_inputs = provider_class.get_initialize_inputs()
        init_inputs_values = {}
        for k, v in node_inputs.items():
            if k not in init_inputs:
                continue
            if v.value_type != InputValueType.LITERAL:
                raise ValueError(
                    f"Input {k!r} for tool '{tool_name}' only supports literal values for initialization,"
                    + f" got {v.serialize()!r}"
                )
            init_inputs_values[k] = v.value
        missing_inputs = set(provider_class.get_required_initialize_inputs()) - set(init_inputs_values)
        if missing_inputs:
            raise MissingRequiredInputs(
                message=f"Required inputs {list(missing_inputs)} are not provided for tool '{tool_name}'.",
                target=ErrorTarget.EXECUTOR,
            )
        # Return the init_inputs to update node inputs in the afterward steps
        return getattr(provider_class(**init_inputs_values), method_name), init_inputs

    @staticmethod
    def load_tool_by_api_name(api_name: str) -> Tool:
        if api_name is None:
            return None
        return BuiltinsManager._load_llm_api(api_name)

    def load_prompt_with_api(self, tool: Tool, api: Tool, node_inputs: Optional[dict] = None) -> Tuple[Callable, dict]:
        """Load a prompt template tool with action."""
        # Load provider action function
        api_func, init_inputs = self.load_builtin(api, node_inputs)
        # Find the prompt template parameter name and parse tool code to it.
        prompt_tpl_param_name = get_prompt_param_name_from_func(api_func)
        api_func = partial(api_func, **{prompt_tpl_param_name: tool.code}) if prompt_tpl_param_name else api_func
        # Return the init_inputs to update node inputs in the afterward steps
        return api_func, init_inputs

    def load_prompt_rendering(self, tool: Tool):
        if not tool.code:
            tool.code = ""
        from promptflow.tools.template_rendering import render_template_jinja2

        return partial(render_template_jinja2, template=tool.code)

    @staticmethod
    def parse_builtin_tool_method(tool: Tool) -> tuple:
        module_name = tool.module
        class_name = tool.class_name
        method_name = tool.function
        return module_name, class_name, method_name

    @staticmethod
    def is_builtin(tool: Tool) -> bool:
        """Check if the tool is a builtin tool."""
        return tool.type is ToolType.PYTHON and tool.code is None and tool.source is None

    @staticmethod
    def is_llm(tool: Tool) -> bool:
        """Check if the tool is a LLM tool."""
        return tool.type is ToolType.LLM

    @staticmethod
    def is_custom_python(tool: Tool) -> bool:
        """Check if the tool is a custom python tool."""
        return tool.type is ToolType.PYTHON and not BuiltinsManager.is_builtin(tool)


class ToolsManager:
    """Manage all builtins and user-defined tools."""

    def __init__(
        self,
        loaded_tools: Optional[Mapping[str, Callable]] = None,
    ) -> None:
        loaded_tools = loaded_tools or {}
        self._tools = {k: v for k, v in loaded_tools.items()}

    def load_tools(self, tools: Mapping[str, Callable]) -> None:
        """Load new tools to the manager."""
        self._tools.update(tools)

    def loaded(self, tool: str) -> bool:
        return tool in self._tools

    def get_tool(self, key: str) -> Callable:
        if key not in self._tools:
            raise ValueError(f"Tool for {key} is not loaded")
        return self._tools[key]

    def wrap_tool(self, key: str, wrapper: Callable):
        """Wraps the tool with specific name by a given wrapper.

        Sometimes we may want to wrap the tool with a decorator, but we don't want to modify the original tool.

        i.e. We may want to pass additional arguments to the tool by wrapping it with a decorator,
             such as turning on the stream response for AzureOpenAI.chat() by adding a "stream=True" argument.
        """
        tool = self.get_tool(key)
        self._tools.update({key: wrapper(tool)})

    def assert_loaded(self, tool: str):
        if tool not in self._tools:
            raise ValueError(f"Tool {tool} is not loaded")

    # Customers are familiar with the term "node", so we use it in error message.
    @staticmethod
    def _load_custom_tool(tool: Tool, node_name: str) -> Callable:
        func_name = tool.function or tool.name
        if tool.source and Path(tool.source).exists():  # If source file is provided, load the function from the file
            m = load_python_module_from_file(tool.source)
            if m is None:
                raise CustomToolSourceLoadError(f"Cannot load module from source {tool.source} for node {node_name}.")
            return getattr(m, func_name)
        if not tool.code:
            raise EmptyCodeInCustomTool(f"Missing code in node {node_name}.")
        func_code = tool.code
        try:
            f_globals = {}
            exec(func_code, f_globals)
        except Exception as e:
            raise CustomPythonToolLoadError(f"Error when loading code of node {node_name}: {e}") from e
        if func_name not in f_globals:
            raise MissingTargetFunction(f"Cannot find function {func_name} in the code of node {node_name}.")
        return f_globals[func_name]


class ToolsLoader:
    def __init__(self, package_tool_keys: Optional[List[str]] = None) -> None:
        self._package_tools = collect_package_tools(package_tool_keys) if package_tool_keys else {}

    def load_tool_for_node(self, node: Node, working_dir: str) -> Tool:
        if node.source is None:
            raise UserErrorException(f"Node {node.name} does not have source defined.")
        if node.type is ToolType.PYTHON:
            if node.source.type == ToolSourceType.Package:
                return self.load_tool_for_package_node(node)
            elif node.source.type == ToolSourceType.Code:
                _, tool = self.load_tool_for_script_node(node, working_dir)
                return tool
            raise NotImplementedError(f"Tool source type {node.source.type} for python tool is not supported yet.")
        elif node.type is ToolType.PROMPT:
            return None
        elif node.type is ToolType.LLM:
            return self.load_tool_for_llm_node(node)
        elif node.type is ToolType.CUSTOM_LLM:
            if node.source.type == ToolSourceType.PackageWithPrompt:
                return self.load_tool_for_package_node(node)
            raise NotImplementedError(
                f"Tool source type {node.source.type} for custom_llm tool is not supported yet."
            )
        else:
            raise NotImplementedError(f"Tool type {node.type} is not supported yet.")

    def load_tool_for_package_node(self, node: Node) -> Tool:
        if node.source.tool in self._package_tools:
            return Tool.deserialize(self._package_tools[node.source.tool])
        raise PackageToolNotFoundError(
            f"Package tool '{node.source.tool}' is not found in the current environment. "
            f"All available package tools are: {list(self._package_tools.keys())}.",
            target=ErrorTarget.EXECUTOR,
        )

    def load_tool_for_script_node(self, node: Node, working_dir: str) -> Tool:
        if node.source.path is None:
            raise UserErrorException(f"Node {node.name} does not have source path defined.")
        path = node.source.path
        m = load_python_module_from_file(working_dir / path)
        if m is None:
            raise CustomToolSourceLoadError(f"Cannot load module from {path}.")
        f = collect_tool_function_in_module(m)
        return f, _parse_tool_from_function(f)

    def load_tool_for_llm_node(self, node: Node) -> Tool:
        api_name = f"{node.provider}.{node.api}"
        return BuiltinsManager._load_llm_api(api_name)


builtins = {}
apis = {}
connections = {}
connection_type_to_api_mapping = {}
reserved_keys = {}


def _register(provider_cls, collection, type):
    from promptflow._core.tool import ToolProvider

    if not issubclass(provider_cls, ToolProvider):
        raise Exception(f"Class {provider_cls.__name__!r} must be a subclass of promptflow.ToolProvider.")
    initialize_inputs = provider_cls.get_initialize_inputs()
    # Build tool/provider definition
    for name, value in provider_cls.__dict__.items():
        if hasattr(value, "__original_function"):
            name = value.__original_function.__qualname__
            value.__tool = function_to_tool_definition(
                value, type=type, initialize_inputs=initialize_inputs
            )
            collection[name] = value.__tool
            module_logger.debug(f"Registered {name} as a builtin function")
    # Get the connection type - provider name mapping for execution use
    # Tools/Providers related connection must have been imported
    for param in initialize_inputs.values():
        if not param.annotation:
            continue
        annotation_type_name = param.annotation.__name__
        if annotation_type_name in connections:
            api_name = provider_cls.__name__
            module_logger.debug(f"Add connection type {annotation_type_name} to api {api_name} mapping")
            connection_type_to_api_mapping[annotation_type_name] = api_name
            break


def _register_method(provider_method, collection, type):
    name = provider_method.__qualname__
    provider_method.__tool = function_to_tool_definition(provider_method, type=type)
    collection[name] = provider_method.__tool
    module_logger.debug(f"Registered {name} as {type} function")


def _get_llm_reserved_keys():
    params = []
    for k, v in apis.items():
        if isinstance(v, Tool):
            params.extend(v.inputs.keys())
    return set(params)


def register_builtins(provider_cls):
    _register(provider_cls, builtins, ToolType.PYTHON)


def register_apis(provider_cls):
    _register(provider_cls, apis, ToolType._ACTION)
    global reserved_keys
    reserved_keys = _get_llm_reserved_keys()


def register_builtin_method(provider_method):
    _register_method(provider_method, builtins, ToolType.PYTHON)


def register_api_method(provider_method):
    _register_method(provider_method, apis, ToolType._ACTION)


def register_connections(connection_classes: Union[type, List[type]]):
    connection_classes = [connection_classes] if not isinstance(connection_classes, list) else connection_classes
    connections.update({cls.__name__: cls for cls in connection_classes})


class CustomToolSourceLoadError(SystemErrorException):
    pass


class CustomToolError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, message):
        super().__init__(message, target=ErrorTarget.TOOL)


class EmptyCodeInCustomTool(CustomToolError):
    pass


class CustomPythonToolLoadError(CustomToolError):
    pass


class MissingTargetFunction(CustomToolError):
    pass


class APINotFound(ValidationException):
    pass


class NodeSourcePathEmpty(ValidationException):
    pass
