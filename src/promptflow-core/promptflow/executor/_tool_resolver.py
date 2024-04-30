# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import inspect
import logging
import types
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, List, Optional

from promptflow._constants import MessageFormatType
from promptflow._core._errors import InvalidSource
from promptflow._core.tool import INPUTS_TO_ESCAPE_PARAM_KEY, STREAMING_OPTION_PARAMETER_ATTR, TOOL_TYPE_TO_ESCAPE
from promptflow._core.tools_manager import BuiltinsManager, ToolLoader, connection_type_to_api_mapping
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow._utils.tool_utils import (
    function_to_interface,
    get_inputs_for_prompt_template,
    get_prompt_param_name_from_func,
)
from promptflow._utils.yaml_utils import load_yaml
from promptflow.connections import ConnectionProvider
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import ConnectionType, Tool, ToolType, ValueType
from promptflow.contracts.types import AssistantDefinition, PromptTemplate
from promptflow.exceptions import ErrorTarget, PromptflowException, UserErrorException
from promptflow.executor._assistant_tool_invoker import (
    AssistantTool,
    AssistantToolInvoker,
    AssistantToolResolver,
    ResolvedAssistantTool,
    to_json_type_mapping,
)
from promptflow.executor._docstring_parser import DocstringParser
from promptflow.executor._errors import (
    EmptyLLMApiMapping,
    FailedToGenerateToolDefinition,
    GetConnectionError,
    InvalidAssistantTool,
    InvalidConnectionType,
    InvalidCustomLLMTool,
    NodeInputValidationError,
    ResolveToolError,
    ValueTypeUnresolved,
)


@dataclass
class ResolvedTool:
    node: Node
    definition: Tool
    callable: Callable
    init_args: dict


class ToolResolver:
    def __init__(
        self,
        working_dir: Path,
        connection_provider: Optional[ConnectionProvider] = None,
        package_tool_keys: Optional[List[str]] = None,
        message_format: str = MessageFormatType.BASIC,
    ):
        try:
            # Import openai and aoai for llm tool
            from promptflow.tools import aoai, openai  # noqa: F401
        except ImportError:
            pass
        self._tool_loader = ToolLoader(working_dir, package_tool_keys=package_tool_keys)
        self._working_dir = working_dir
        self._connection_provider = connection_provider
        self._multimedia_processor = MultimediaProcessor.create(message_format)

    @classmethod
    def start_resolver(
        cls, working_dir: Path, connections: Optional[dict] = None, package_tool_keys: Optional[List[str]] = None
    ):
        resolver = cls(working_dir, connections, package_tool_keys)
        resolver._activate_in_context(force=True)
        return resolver

    def _convert_to_connection_value(self, k: str, v: InputAssignment, node_name: str, conn_types: List[ValueType]):
        try:
            connection_value = self._connection_provider.get(v.value)
        except Exception as e:  # Cache all exception as different provider raises different exceptions
            # Raise new error with node details
            raise GetConnectionError(v.value, node_name, e) from e
        # Check if type matched
        if not any(type(connection_value).__name__ == typ for typ in conn_types):
            msg = (
                f"Input '{k}' for node '{node_name}' of type {type(connection_value).__name__!r}"
                f" is not supported, valid types {conn_types}."
            )
            raise NodeInputValidationError(message=msg)
        return connection_value

    def _convert_to_custom_strong_type_connection_value(
        self,
        k: str,
        v: InputAssignment,
        node_name: str,
        source: ToolSource,
        tool: Tool,
        conn_types: List[str],
        module: types.ModuleType,
    ):
        if not conn_types:
            msg = f"Input '{k}' for node '{node_name}' has invalid types: {conn_types}."
            raise NodeInputValidationError(message=msg)
        try:
            connection_value = self._connection_provider.get(v.value)
        except Exception as e:  # Cache all exception as different provider raises different exceptions
            # Raise new error with node details
            raise GetConnectionError(v.value, node_name, e) from e

        custom_defined_connection_class_name = conn_types[0]
        source_type = getattr(source, "type", None)
        if source_type == ToolSourceType.Package:
            module = tool.module
        return connection_value._convert_to_custom_strong_type(
            module=module, to_class=custom_defined_connection_class_name
        )

    def _convert_to_assistant_definition(self, assistant_definition_path: str, input_name: str, node_name: str):
        if assistant_definition_path is None or not (self._working_dir / assistant_definition_path).is_file():
            raise InvalidSource(
                target=ErrorTarget.EXECUTOR,
                message_format="Input '{input_name}' for node '{node_name}' of value '{source_path}' "
                "is not a valid path.",
                input_name=input_name,
                source_path=assistant_definition_path,
                node_name=node_name,
            )
        file = self._working_dir / assistant_definition_path
        with open(file, "r", encoding="utf-8") as file:
            assistant_definition = load_yaml(file)
        assistant_def = AssistantDefinition.deserialize(assistant_definition)
        self._resolve_assistant_tools(node_name, assistant_def)
        return assistant_def

    def _resolve_assistant_tools(self, node_name: str, assistant_definition: AssistantDefinition):
        """
        Resolves AssistantTool from the raw assistant definition.

        The assistant definition is initialized with a path or package to source file.
        This method loads scripts/module, parses the structure into AssistantTool instances for future invoking.
        It supports tools of types 'code_interpreter' and 'retrieval' directly and loads 'function' type tools
        as callable functions. Unsupported tool types raise an exception.
        """
        resolved_tools = {}
        for tool in assistant_definition.tools:
            if tool["type"] in ("code_interpreter", "retrieval"):
                resolved_tools[tool["type"]] = ResolvedAssistantTool(
                    name=tool["type"], openai_definition=tool, func=None
                )
            elif tool["type"] == "function":
                assistant_tool = AssistantToolResolver.from_dict(tool, node_name)
                function_tool = self.resolve_function_by_definition(node_name, assistant_tool)
                resolved_tools[function_tool.name] = function_tool
            else:
                raise InvalidAssistantTool(
                    message_format=(
                        "Unsupported assistant tool's type in node {node_name} : {type}. "
                        "Please make sure the type is restricted within "
                        "['code_interpreter', 'function', 'retrieval']."
                    ),
                    type=type,
                    target=ErrorTarget.EXECUTOR,
                )
        # Inject the resolved tools into the assistant definition
        assistant_definition._tool_invoker = AssistantToolInvoker(resolved_tools)

    def _resolve_predefined_inputs_type(self, node_name: str, assistant_tool: AssistantTool, tool: Tool):
        predefined_inputs = {}
        if assistant_tool.predefined_inputs:
            for input_name, value in assistant_tool.predefined_inputs.items():
                predefined_inputs[input_name] = InputAssignment.deserialize(value)

        source = assistant_tool.source
        updated_predefined_inputs = self._convert_literal_input_types(node_name, source, predefined_inputs, tool)
        return updated_predefined_inputs

    def _construct_assistant_tool(
        self, tool: Tool, callable: Callable, predefined_inputs: dict
    ) -> ResolvedAssistantTool:
        func_name = tool.function
        definition = self._generate_assistant_tool_definition(tool, callable, predefined_inputs)
        if predefined_inputs:
            inputs = {name: value.value for name, value in predefined_inputs.items()}
            func = partial(callable, **inputs)
        else:
            func = callable
        return ResolvedAssistantTool(name=func_name, openai_definition=definition, func=func)

    def _load_package_tool_as_function(self, node_name: str, assistant_tool: AssistantTool) -> ResolvedAssistantTool:
        """Get assistant function from package tool definition."""

        # Step I: construct promptflow Tool object from the source:tool specification
        source_tool = assistant_tool.source.tool
        function_package_tool_keys = [source_tool]
        tool_loader = ToolLoader(self._working_dir, function_package_tool_keys)
        tool: Tool = tool_loader.load_package_tool(source_tool)

        # Step II: resolve the predefined_inputs if necessary
        updated_predefined_inputs = self._resolve_predefined_inputs_type(node_name, assistant_tool, tool)

        # Step III: import the package tool and return the callable & init_args
        callable, init_args = BuiltinsManager._load_package_tool(
            tool.name, tool.module, tool.class_name, tool.function, updated_predefined_inputs
        )
        self._remove_init_args(updated_predefined_inputs, init_args)

        # Step IV: construct the AssistantTool object from the updated predefined_inputs + Tool object
        return self._construct_assistant_tool(tool, callable, updated_predefined_inputs)

    def _load_script_tool_as_function(self, node_name: str, assistant_tool: AssistantTool) -> ResolvedAssistantTool:
        """Get assistant function from script tool definition."""

        # Step I: construct promptflow Tool object from the source:path specification
        source_path = assistant_tool.source.path
        m, tool = self._tool_loader.load_script_tool(source_path, node_name)

        # Step II: resolve the predefined_inputs if necessary
        updated_predefined_inputs = self._resolve_predefined_inputs_type(node_name, assistant_tool, tool)

        # Step III: import the python tool and return the callable & init_args
        callable, init_args = BuiltinsManager._load_tool_from_module(
            m, tool.name, tool.module, tool.class_name, tool.function, updated_predefined_inputs
        )
        self._remove_init_args(updated_predefined_inputs, init_args)

        # Step IV: construct the AssistantTool object from the updated predefined_inputs + Tool object
        return self._construct_assistant_tool(tool, callable, updated_predefined_inputs)

    def _generate_assistant_tool_definition(self, tool: Tool, func: Callable, predefined_inputs: dict) -> dict:
        try:
            # Attempt to extract the description, handling exceptions
            try:
                description, param_descriptions = DocstringParser.parse_description(func.__doc__)
            except Exception as e:
                # Log the exception if necessary
                logging.warning(f"Failed to parse docstring for function {func.__name__}: {e}")
                # Set description to None or an empty string
                description = None  # or description = ""
                param_descriptions = {}

            func_definition = {
                "name": func.__name__,
                "description": description,
                "parameters": {"type": "object", "properties": {}, "required": []},
            }

            inputs, _, _, _ = function_to_interface(func)
            for name, param in inputs.items():
                if name in predefined_inputs:
                    # Exclude predefined inputs from definition generation
                    continue
                # Determine if parameter is required (has no default value)
                is_required = param.default is None
                if is_required:
                    func_definition["parameters"]["required"].append(name)

                # Get parameter type and convert to JSON type
                param_type = param.type[0]
                json_type = to_json_type_mapping.get(param_type, "object")

                # Construct parameter definition
                func_definition["parameters"]["properties"][name] = {
                    "type": json_type,
                    "description": param_descriptions.get(name, {}).get("description", ""),
                }

                # Handle enums separately to include possible values
                if tool.inputs[name].enum:
                    func_definition["parameters"]["properties"][name]["enum"] = tool.inputs[name].enum

            return {
                "type": "function",
                "function": func_definition,
            }
        except Exception as e:
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            raise FailedToGenerateToolDefinition(
                message_format=(
                    "Failed to generate openai tool definition for function '{func_name}'. "
                    "Error: {error_type_and_message}."
                ),
                func_name=func.__name__,
                error_type_and_message=error_type_and_message,
                target=ErrorTarget.EXECUTOR,
            ) from e

    def _convert_literal_input_types(
        self, node_name: str, source: ToolSource, inputs: dict, tool: Tool, module: types.ModuleType = None
    ):
        updated_inputs = {
            k: v
            for k, v in inputs.items()
            if (v.value is not None and v.value != "") or v.value_type != InputValueType.LITERAL
        }
        for k, v in updated_inputs.items():
            if v.value_type != InputValueType.LITERAL:
                continue
            tool_input = tool.inputs.get(k)
            if tool_input is None:  # For kwargs input, tool_input is None.
                continue
            value_type = tool_input.type[0]
            updated_inputs[k] = InputAssignment(value=v.value, value_type=InputValueType.LITERAL)
            if ConnectionType.is_connection_class_name(value_type):
                if tool_input.custom_type:
                    updated_inputs[k].value = self._convert_to_custom_strong_type_connection_value(
                        k, v, node_name, source, tool, tool_input.custom_type, module=module
                    )
                else:
                    updated_inputs[k].value = self._convert_to_connection_value(k, v, node_name, tool_input.type)
            elif value_type == ValueType.IMAGE:
                try:
                    updated_inputs[k].value = self._multimedia_processor.create_image(v.value)
                except Exception as e:
                    error_type_and_message = f"({e.__class__.__name__}) {e}"
                    raise NodeInputValidationError(
                        message_format="Failed to load image for input '{key}': {error_type_and_message}",
                        key=k,
                        error_type_and_message=error_type_and_message,
                        target=ErrorTarget.EXECUTOR,
                    ) from e
            elif value_type == ValueType.ASSISTANT_DEFINITION:
                try:
                    updated_inputs[k].value = self._convert_to_assistant_definition(v.value, k, node_name)
                except Exception as e:
                    error_type_and_message = f"({e.__class__.__name__}) {e}"
                    raise NodeInputValidationError(
                        message_format="Failed to load assistant definition from input '{key}': "
                        "{error_type_and_message}",
                        key=k,
                        error_type_and_message=error_type_and_message,
                        target=ErrorTarget.EXECUTOR,
                    ) from e
            elif isinstance(value_type, ValueType):
                try:
                    updated_inputs[k].value = value_type.parse(v.value)
                except Exception as e:
                    raise NodeInputValidationError(
                        message_format="Input '{key}' for node '{node_name}' of value '{value}' is not "
                        "type {value_type}.",
                        key=k,
                        node_name=node_name,
                        value=v.value,
                        value_type=value_type.value,
                        target=ErrorTarget.EXECUTOR,
                    ) from e
                try:
                    updated_inputs[k].value = self._multimedia_processor.load_multimedia_data_recursively(
                        updated_inputs[k].value
                    )
                except Exception as e:
                    error_type_and_message = f"({e.__class__.__name__}) {e}"
                    raise NodeInputValidationError(
                        message_format="Failed to load image for input '{key}': {error_type_and_message}",
                        key=k,
                        error_type_and_message=error_type_and_message,
                        target=ErrorTarget.EXECUTOR,
                    ) from e
            else:
                # The value type is in ValueType enum or is connection type. null connection has been handled before.
                raise ValueTypeUnresolved(
                    f"Unresolved input type {value_type!r}, please check if it is supported in current version.",
                    target=ErrorTarget.EXECUTOR,
                )
        return updated_inputs

    def _convert_node_literal_input_types(self, node: Node, tool: Tool, module: types.ModuleType = None):
        updated_node = copy.deepcopy(node)
        updated_node.inputs = self._convert_literal_input_types(node.name, node.source, node.inputs, tool, module)
        return updated_node

    def resolve_tool_by_node(self, node: Node, convert_input_types=True) -> ResolvedTool:
        try:
            if node.source is None:
                raise UserErrorException(f"Node {node.name} does not have source defined.")

            if node.type is ToolType.PYTHON:
                if node.source.type == ToolSourceType.Package:
                    return self._resolve_package_node(node, convert_input_types=convert_input_types)
                elif node.source.type == ToolSourceType.Code:
                    return self._resolve_script_node(node, convert_input_types=convert_input_types)
                raise NotImplementedError(f"Tool source type {node.source.type} for python tool is not supported yet.")
            elif node.type is ToolType.PROMPT:
                return self._resolve_prompt_node(node)
            elif node.type is ToolType.LLM:
                return self._resolve_llm_node(node, convert_input_types=convert_input_types)
            elif node.type is ToolType.CUSTOM_LLM:
                if node.source.type == ToolSourceType.PackageWithPrompt:
                    resolved_tool = self._resolve_package_node(node, convert_input_types=convert_input_types)
                    return self._integrate_prompt_in_package_node(resolved_tool)
                raise NotImplementedError(
                    f"Tool source type {node.source.type} for custom_llm tool is not supported yet."
                )
            else:
                raise NotImplementedError(f"Tool type {node.type} is not supported yet.")
        except Exception as e:
            if isinstance(e, PromptflowException) and e.target != ErrorTarget.UNKNOWN:
                raise ResolveToolError(node_name=node.name, target=e.target, module=e.module) from e
            raise ResolveToolError(node_name=node.name) from e

    def resolve_function_by_definition(self, node_name: str, tool: AssistantTool) -> ResolvedAssistantTool:
        try:
            source_type = tool.source.type
            if source_type == ToolSourceType.Package:
                return self._load_package_tool_as_function(node_name, tool)
            elif source_type == ToolSourceType.Code:
                return self._load_script_tool_as_function(node_name, tool)
            raise InvalidAssistantTool(
                message_format=(
                    "Tool source type {source_type} is not supported in assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct."
                ),
                node_name=node_name,
                source_type=source_type.value,
                target=ErrorTarget.EXECUTOR,
            )
        except Exception as e:
            if isinstance(e, PromptflowException) and e.target != ErrorTarget.UNKNOWN:
                raise ResolveToolError(node_name=node_name, target=e.target, module=e.module) from e
            raise ResolveToolError(node_name=node_name) from e

    def _load_source_content(self, node: Node) -> str:
        source = node.source
        # If is_file returns True, the path points to a existing file, so we don't need to check if exists.
        if source is None or source.path is None or not (self._working_dir / source.path).is_file():
            raise InvalidSource(
                target=ErrorTarget.EXECUTOR,
                message_format="Node source path '{source_path}' is invalid on node '{node_name}'.",
                source_path=source.path if source is not None else None,
                node_name=node.name,
            )
        file = self._working_dir / source.path
        return file.read_text(encoding="utf-8")

    def _validate_duplicated_inputs(self, prompt_tpl_inputs: list, tool_params: list, msg: str):
        duplicated_inputs = set(prompt_tpl_inputs) & set(tool_params)
        if duplicated_inputs:
            raise NodeInputValidationError(
                message=msg.format(duplicated_inputs=duplicated_inputs),
                target=ErrorTarget.EXECUTOR,
            )

    def _load_images_for_prompt_tpl(self, prompt_tpl_inputs_mapping: dict, node_inputs: dict):
        for input_name, input in prompt_tpl_inputs_mapping.items():
            if ValueType.IMAGE in input.type and input_name in node_inputs:
                if node_inputs[input_name].value_type == InputValueType.LITERAL:
                    node_inputs[input_name].value = self._multimedia_processor.create_image(
                        node_inputs[input_name].value
                    )
        return node_inputs

    def _resolve_prompt_node(self, node: Node) -> ResolvedTool:
        prompt_tpl = self._load_source_content(node)
        prompt_tpl_inputs_mapping = get_inputs_for_prompt_template(prompt_tpl)
        from promptflow.tools.template_rendering import render_template_jinja2

        params = inspect.signature(render_template_jinja2).parameters
        param_names = [name for name, param in params.items() if param.kind != inspect.Parameter.VAR_KEYWORD]
        msg = (
            f"Invalid inputs {{duplicated_inputs}} in prompt template of node {node.name}. "
            f"These inputs are duplicated with the reserved parameters of prompt tool."
        )
        self._validate_duplicated_inputs(prompt_tpl_inputs_mapping.keys(), param_names, msg)
        node.inputs = self._load_images_for_prompt_tpl(prompt_tpl_inputs_mapping, node.inputs)
        self._update_inputs_to_escape(node)

        callable = partial(render_template_jinja2, template=prompt_tpl)
        return ResolvedTool(node=node, definition=None, callable=callable, init_args={})

    @staticmethod
    def _remove_init_args(node_inputs: dict, init_args: dict):
        for k in init_args:
            if k in node_inputs:
                del node_inputs[k]

    def _get_llm_node_connection(self, node: Node):
        try:
            connection = self._connection_provider.get(node.connection)
        except Exception as e:  # Cache all exception as different provider raises different exceptions
            # Raise new error with node details
            raise GetConnectionError(node.connection, node.name, e) from e
        return connection

    @staticmethod
    def _resolve_llm_connection_with_provider(connection):
        if not connection_type_to_api_mapping:
            raise EmptyLLMApiMapping()
        # If provider is not specified, try to resolve it from connection type
        connection_type = type(connection).__name__
        if connection_type not in connection_type_to_api_mapping:
            from promptflow.connections import OpenAIConnection, ServerlessConnection

            # This is a fallback for the case that ServerlessConnection related tool is not ready
            # in legacy versions, then we can directly use OpenAIConnection.
            if isinstance(connection, ServerlessConnection):
                # The ServerlessConnection should be passed into promptflow-tools as it is.
                # And this append "/v1" logic should exist in promptflow-tools.
                # But since old version promptflow package doesn't support below things:
                # 1. There is NO ServerlessConnection;
                # 2. Register_apis doesn't support Union;
                # So in order to release this append "/v1" function without breaking old promptflow package.
                # We move this logic here.
                # This is a short-term solution. After MaaS supports OpenAI compatible rest API,
                # we should remove the V1 tricky here.
                suffix = "/v1"
                base_url = connection.api_base
                if not base_url.endswith(suffix):
                    # append "/v1" to ServerlessConnection api_base so that it can directly use the OpenAI SDK.
                    base_url += suffix
                connection = OpenAIConnection(
                    api_key=connection.api_key,
                    base_url=base_url,
                    name=connection.name,
                )
                connection_type = "OpenAIConnection"
            else:
                raise InvalidConnectionType(
                    message_format="Connection type {conn_type} is not supported for LLM.",
                    conn_type=connection_type,
                )
        provider = connection_type_to_api_mapping[connection_type]
        return connection, provider

    def _update_inputs_to_escape(self, node: Node):
        # Store flow inputs list as a node input to enable tools to identify these inputs,
        # and apply escape/unescape to avoid parsing of role in user inputs.
        inputs_to_escape = []
        inputs = node.inputs
        if node.type in TOOL_TYPE_TO_ESCAPE:
            for k, v in inputs.items():
                if v.value_type == InputValueType.FLOW_INPUT:
                    inputs_to_escape.append(k)

        if inputs_to_escape:
            node.inputs[INPUTS_TO_ESCAPE_PARAM_KEY] = InputAssignment(
                value=inputs_to_escape, value_type=InputValueType.LITERAL
            )

    def _resolve_llm_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        connection, provider = self._resolve_llm_connection_with_provider(self._get_llm_node_connection(node))
        # Always set the provider according to the connection type
        # to make sure the invoking logic is consistent between the connection and the tool.
        node.provider = provider
        tool: Tool = self._tool_loader.load_tool_for_llm_node(node)
        key, connection = self._resolve_llm_connection_to_inputs(node, tool, connection)
        updated_node = copy.deepcopy(node)
        updated_node.inputs[key] = InputAssignment(value=connection, value_type=InputValueType.LITERAL)
        if convert_input_types:
            updated_node = self._convert_node_literal_input_types(updated_node, tool)

        self._update_inputs_to_escape(updated_node)

        prompt_tpl = self._load_source_content(node)
        prompt_tpl_inputs_mapping = get_inputs_for_prompt_template(prompt_tpl)
        msg = (
            f"Invalid inputs {{duplicated_inputs}} in prompt template of node {node.name}. "
            f"These inputs are duplicated with the parameters of {node.provider}.{node.api}."
        )
        self._validate_duplicated_inputs(prompt_tpl_inputs_mapping.keys(), tool.inputs.keys(), msg)
        updated_node.inputs = self._load_images_for_prompt_tpl(prompt_tpl_inputs_mapping, updated_node.inputs)
        api_func, init_args = BuiltinsManager._load_package_tool(
            tool.name, tool.module, tool.class_name, tool.function, updated_node.inputs
        )
        self._remove_init_args(updated_node.inputs, init_args)
        prompt_tpl_param_name = get_prompt_param_name_from_func(api_func)
        api_func = partial(api_func, **{prompt_tpl_param_name: prompt_tpl}) if prompt_tpl_param_name else api_func
        return ResolvedTool(updated_node, tool, api_func, init_args)

    def _resolve_llm_connection_to_inputs(self, node: Node, tool: Tool, connection=None) -> Node:
        # No need to get connection if it is already provided
        # TODO: Refine the code here since the connection would always be provided.
        connection = connection or self._get_llm_node_connection(node)
        for key, input in tool.inputs.items():
            if ConnectionType.is_connection_class_name(input.type[0]):
                if type(connection).__name__ not in input.type:
                    msg = (
                        f"Invalid connection '{node.connection}' type {type(connection).__name__!r} "
                        f"for node '{node.name}', valid types {input.type}."
                    )
                    raise InvalidConnectionType(message=msg)
                return key, connection
        raise InvalidConnectionType(
            message_format="Connection type can not be resolved for tool {tool_name}", tool_name=tool.name
        )

    def _resolve_script_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        m, tool = self._tool_loader.load_tool_for_script_node(node)
        # We only want to load script tool module once.
        # Reloading the same module changes the ID of the class, which can cause issues with isinstance() checks.
        # This is important when working with connection class checks. For instance, in user tool script it writes:
        #       isinstance(conn, MyCustomConnection)
        # Custom defined script tool and custom defined strong type connection are in the same module.
        # The first time to load the module is in above line when loading a tool.
        # We need the module again when converting the custom connection to strong type when converting input types.
        # To avoid reloading, pass the loaded module to _convert_node_literal_input_types as an arg.
        if convert_input_types:
            node = self._convert_node_literal_input_types(node, tool, m)
        callable, init_args = BuiltinsManager._load_tool_from_module(
            m, tool.name, tool.module, tool.class_name, tool.function, node.inputs
        )
        self._remove_init_args(node.inputs, init_args)
        return ResolvedTool(node=node, definition=tool, callable=callable, init_args=init_args)

    def _resolve_package_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        tool: Tool = self._tool_loader.load_tool_for_package_node(node)
        updated_node = copy.deepcopy(node)
        if convert_input_types:
            updated_node = self._convert_node_literal_input_types(updated_node, tool)
        self._update_inputs_to_escape(updated_node)

        callable, init_args = BuiltinsManager._load_package_tool(
            tool.name, tool.module, tool.class_name, tool.function, updated_node.inputs
        )
        self._remove_init_args(updated_node.inputs, init_args)
        return ResolvedTool(node=updated_node, definition=tool, callable=callable, init_args=init_args)

    def _integrate_prompt_in_package_node(self, resolved_tool: ResolvedTool):
        node = resolved_tool.node
        prompt_tpl = PromptTemplate(self._load_source_content(node))
        prompt_tpl_inputs_mapping = get_inputs_for_prompt_template(prompt_tpl)
        msg = (
            f"Invalid inputs {{duplicated_inputs}} in prompt template of node {node.name}. "
            f"These inputs are duplicated with the inputs of custom llm tool."
        )
        self._validate_duplicated_inputs(prompt_tpl_inputs_mapping.keys(), resolved_tool.definition.inputs.keys(), msg)
        node.inputs = self._load_images_for_prompt_tpl(prompt_tpl_inputs_mapping, node.inputs)
        callable = resolved_tool.callable
        prompt_tpl_param_name = get_prompt_param_name_from_func(callable)
        if prompt_tpl_param_name is None:
            raise InvalidCustomLLMTool(
                f"Invalid Custom LLM tool {resolved_tool.definition.name}: "
                f"function {callable.__name__} is missing a prompt template argument.",
                target=ErrorTarget.EXECUTOR,
            )
        resolved_tool.callable = partial(callable, **{prompt_tpl_param_name: prompt_tpl})
        #  Copy the attributes to make sure they are still available after partial.
        attributes_to_set = [STREAMING_OPTION_PARAMETER_ATTR]
        for attr in attributes_to_set:
            attr_val = getattr(callable, attr, None)
            if attr_val is not None:
                setattr(resolved_tool.callable, attr, attr_val)
        return resolved_tool
