# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from promptflow._constants import DEFAULT_ENCODING, LANGUAGE_KEY, FlowLanguage, MessageFormatType
from promptflow._utils.utils import _match_reference, _sanitize_python_variable_name, try_import
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts._errors import FlowDefinitionError
from promptflow.exceptions import ErrorTarget
from promptflow.tracing._utils import serialize

from ._errors import FailedToImportModule
from .tool import ConnectionType, Tool, ToolType, ValueType

logger = logging.getLogger(__name__)


class InputValueType(Enum):
    """The enum of input value type."""

    LITERAL = "Literal"
    FLOW_INPUT = "FlowInput"
    NODE_REFERENCE = "NodeReference"


FLOW_INPUT_PREFIX = "flow."
FLOW_INPUT_PREFIXES = [FLOW_INPUT_PREFIX, "inputs."]  # Use a list for backward compatibility


@dataclass
class InputAssignment:
    """This class represents the assignment of an input value.

    :param value: The value of the input assignment.
    :type value: Any
    :param value_type: The type of the input assignment.
    :type value_type: ~promptflow.contracts.flow.InputValueType
    :param section: The section of the input assignment, usually the output.
    :type section: str
    :param property: The property of the input assignment that exists in the section.
    :type property: str
    """

    value: Any
    value_type: InputValueType = InputValueType.LITERAL
    section: str = ""
    property: str = ""

    def serialize(self):
        """Serialize the input assignment to a string."""
        if self.value_type == InputValueType.FLOW_INPUT:
            return f"${{{FLOW_INPUT_PREFIX}{self.value}}}"
        elif self.value_type == InputValueType.NODE_REFERENCE:
            if self.property:
                return f"${{{self.value}.{self.section}.{self.property}}}"
            return f"${{{self.value}.{self.section}}}"
        elif ConnectionType.is_connection_value(self.value):
            return ConnectionType.serialize_conn(self.value)
        return self.value

    @staticmethod
    def deserialize(value: str) -> "InputAssignment":
        """Deserialize the input assignment from a string.

        :param value: The string to be deserialized.
        :type value: str
        :return: The input assignment constructed from the string.
        :rtype: ~promptflow.contracts.flow.InputAssignment
        """
        literal_value = InputAssignment(value, InputValueType.LITERAL)
        if isinstance(value, str) and value.startswith("$") and len(value) > 2:
            value = value[1:]
            if value[0] != "{" or value[-1] != "}":
                return literal_value
            value = value[1:-1]
            return InputAssignment.deserialize_reference(value)
        return literal_value

    @staticmethod
    def deserialize_reference(value: str) -> "InputAssignment":
        """Deserialize the reference(including node/flow reference) part of an input assignment.

        :param value: The string to be deserialized.
        :type value: str
        :return: The input assignment of reference types.
        :rtype: ~promptflow.contracts.flow.InputAssignment
        """
        if FlowInputAssignment.is_flow_input(value):
            return FlowInputAssignment.deserialize(value)
        return InputAssignment.deserialize_node_reference(value)

    @staticmethod
    def deserialize_node_reference(data: str) -> "InputAssignment":
        """Deserialize the node reference part of an input assignment.

        :param data: The string to be deserialized.
        :type data: str
        :return: Input assignment of node reference type.
        :rtype: ~promptflow.contracts.flow.InputAssignment
        """
        value_type = InputValueType.NODE_REFERENCE
        if "." not in data:
            return InputAssignment(data, value_type, "output")
        node_name, port_name = data.split(".", 1)
        if "." not in port_name:
            return InputAssignment(node_name, value_type, port_name)
        section, property = port_name.split(".", 1)
        return InputAssignment(node_name, value_type, section, property)


@dataclass
class FlowInputAssignment(InputAssignment):
    """This class represents the assignment of a flow input value.

    :param prefix: The prefix of the flow input.
    :type prefix: str
    """

    prefix: str = FLOW_INPUT_PREFIX

    @staticmethod
    def is_flow_input(input_value: str) -> bool:
        """Check whether the input value is a flow input.

        :param input_value: The input value to be checked.
        :type input_value: str
        :return: Whether the input value is a flow input.
        :rtype: bool
        """
        for prefix in FLOW_INPUT_PREFIXES:
            if input_value.startswith(prefix):
                return True
        return False

    @staticmethod
    def deserialize(value: str) -> "FlowInputAssignment":
        """Deserialize the flow input assignment from a string.

        :param value: The string to be deserialized.
        :type value: str
        :return: The flow input assignment constructed from the string.
        :rtype: ~promptflow.contracts.flow.FlowInputAssignment
        """
        for prefix in FLOW_INPUT_PREFIXES:
            if value.startswith(prefix):
                return FlowInputAssignment(
                    value=value[len(prefix) :], value_type=InputValueType.FLOW_INPUT, prefix=prefix
                )
        raise ValueError(f"Unexpected flow input value {value}")


class ToolSourceType(str, Enum):
    """The enum of tool source type."""

    Code = "code"
    Package = "package"
    PackageWithPrompt = "package_with_prompt"


@dataclass
class ToolSource:
    """This class represents the source of a tool.

    :param type: The type of the tool source.
    :type type: ~promptflow.contracts.flow.ToolSourceType
    :param tool: The tool of the tool source.
    :type tool: str
    :param path: The path of the tool source.
    :type path: str
    """

    type: ToolSourceType = ToolSourceType.Code
    tool: Optional[str] = None
    path: Optional[str] = None

    @staticmethod
    def deserialize(data: dict) -> "ToolSource":
        """Deserialize the tool source from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The tool source constructed from the dict.
        :rtype: ~promptflow.contracts.flow.ToolSource
        """
        result = ToolSource(data.get("type", ToolSourceType.Code.value))
        if "tool" in data:
            result.tool = data["tool"]
        if "path" in data:
            result.path = data["path"]
        return result


@dataclass
class ActivateCondition:
    """This class represents the activate condition of a node.

    :param condition: The condition of the activate condition.
    :type condition: ~promptflow.contracts.flow.InputAssignment
    :param condition_value: The value of the condition.
    :type condition_value: Any
    """

    condition: InputAssignment
    condition_value: Any

    @staticmethod
    def deserialize(data: dict, node_name: str = None) -> "ActivateCondition":
        """Deserialize the activate condition from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The activate condition constructed from the dict.
        :rtype: ~promptflow.contracts.flow.ActivateCondition
        """
        node_name = node_name if node_name else ""
        if "when" in data and "is" in data:
            if data["when"] is None and data["is"] is None:
                logger.warning(
                    f"The activate config for node {node_name} has empty 'when' and 'is'. "
                    "Please check your flow yaml to ensure it aligns with your expectations."
                )
            return ActivateCondition(
                condition=InputAssignment.deserialize(data["when"]),
                condition_value=data["is"],
            )
        else:
            raise FlowDefinitionError(
                message_format=(
                    "The definition of activate config for node {node_name} "
                    "is incorrect. Please check your flow yaml and resubmit."
                ),
                node_name=node_name,
            )


@dataclass
class Node:
    """This class represents a node in a flow.

    :param name: The name of the node.
    :type name: str
    :param tool: The tool of the node.
    :type tool: str
    :param inputs: The inputs of the node.
    :type inputs: Dict[str, InputAssignment]
    :param comment: The comment of the node.
    :type comment: str
    :param api: The api of the node.
    :type api: str
    :param provider: The provider of the node.
    :type provider: str
    :param module: The module of the node.
    :type module: str
    :param connection: The connection of the node.
    :type connection: str
    :param aggregation: Whether the node is an aggregation node.
    :type aggregation: bool
    :param enable_cache: Whether the node enable cache.
    :type enable_cache: bool
    :param use_variants: Whether the node use variants.
    :type use_variants: bool
    :param source: The source of the node.
    :type source: ~promptflow.contracts.flow.ToolSource
    :param type: The tool type of the node.
    :type type: ~promptflow.contracts.tool.ToolType
    :param activate: The activate condition of the node.
    :type activate: ~promptflow.contracts.flow.ActivateCondition
    """

    name: str
    tool: str
    inputs: Dict[str, InputAssignment]
    comment: str = ""
    api: str = None
    provider: str = None
    module: str = None  # The module of provider to import
    connection: str = None
    aggregation: bool = False
    enable_cache: bool = False
    use_variants: bool = False
    source: Optional[ToolSource] = None
    type: Optional[ToolType] = None
    activate: Optional[ActivateCondition] = None

    def serialize(self):
        """Serialize the node to a dict.

        :return: The dict of the node.
        :rtype: dict
        """
        data = asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v})
        self.inputs = self.inputs or {}
        data.update({"inputs": {name: i.serialize() for name, i in self.inputs.items()}})
        if self.aggregation:
            data["aggregation"] = True
            data["reduce"] = True  # TODO: Remove this fallback.
        if self.type:
            data["type"] = self.type.value
        return data

    @staticmethod
    def deserialize(data: dict) -> "Node":
        """Deserialize the node from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The node constructed from the dict.
        :rtype: ~promptflow.contracts.flow.Node
        """
        node = Node(
            name=data.get("name"),
            tool=data.get("tool"),
            inputs={name: InputAssignment.deserialize(v) for name, v in (data.get("inputs") or {}).items()},
            comment=data.get("comment", ""),
            api=data.get("api", None),
            provider=data.get("provider", None),
            module=data.get("module", None),
            connection=data.get("connection", None),
            aggregation=data.get("aggregation", False) or data.get("reduce", False),  # TODO: Remove this fallback.
            enable_cache=data.get("enable_cache", False),
            use_variants=data.get("use_variants", False),
        )
        if "source" in data:
            node.source = ToolSource.deserialize(data["source"])
        if "type" in data:
            node.type = ToolType(data["type"])
        if "activate" in data:
            node.activate = ActivateCondition.deserialize(data["activate"], node.name)
        return node


@dataclass
class FlowParamDefinitionBase:
    """Base class for the definition of a flow param (input & init kwargs)."""

    type: ValueType
    default: str = None
    description: str = None

    def serialize(self):
        """Serialize the flow param definition to a dict.

        :return: The dict of the flow param definition.
        :rtype: dict
        """
        data = {}
        data["type"] = self.type.value
        if self.default:
            data["default"] = str(self.default)
        if self.description:
            data["description"] = self.description
        return data


@dataclass
class FlowInputDefinition(FlowParamDefinitionBase):
    """This class represents the definition of a flow input.

    :param type: The type of the flow input.
    :type type: ~promptflow.contracts.tool.ValueType
    :param default: The default value of the flow input.
    :type default: str
    :param description: The description of the flow input.
    :type description: str
    :param enum: The enum of the flow input.
    :type enum: List[str]
    :param is_chat_input: Whether the flow input is a chat input.
    :type is_chat_input: bool
    :param is_chat_history: Whether the flow input is a chat history.
    :type is_chat_history: bool
    """

    enum: List[str] = None
    is_chat_input: bool = False
    is_chat_history: bool = None

    def serialize(self):
        """Serialize the flow input definition to a dict.

        :return: The dict of the flow input definition.
        :rtype: dict
        """
        data = super().serialize()
        if self.enum:
            data["enum"] = self.enum
        if self.is_chat_input:
            data["is_chat_input"] = True
        if self.is_chat_history:
            data["is_chat_history"] = True
        return data

    @staticmethod
    def deserialize(data: dict) -> "FlowInputDefinition":
        """Deserialize the flow input definition from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow input definition constructed from the dict.
        :rtype: ~promptflow.contracts.flow.FlowInputDefinition
        """
        return FlowInputDefinition(
            ValueType(data["type"]),
            data.get("default", None),
            data.get("description", ""),
            data.get("enum", []),
            data.get("is_chat_input", False),
            data.get("is_chat_history", None),
        )


@dataclass
class FlowOutputDefinition:
    """This class represents the definition of a flow output.

    :param type: The type of the flow output.
    :type type: ~promptflow.contracts.tool.ValueType
    :param reference: The reference of the flow output.
    :type reference: ~promptflow.contracts.flow.InputAssignment
    :param description: The description of the flow output.
    :type description: str
    :param evaluation_only: Whether the flow output is for evaluation only.
    :type evaluation_only: bool
    :param is_chat_output: Whether the flow output is a chat output.
    :type is_chat_output: bool
    """

    type: ValueType
    reference: InputAssignment
    description: str = ""
    evaluation_only: bool = False
    is_chat_output: bool = False

    def serialize(self):
        """Serialize the flow output definition to a dict.

        :return: The dict of the flow output definition.
        :rtype: dict
        """
        data = {}
        data["type"] = self.type.value
        if self.reference:
            data["reference"] = self.reference.serialize()
        if self.description:
            data["description"] = self.description
        if self.evaluation_only:
            data["evaluation_only"] = True
        if self.is_chat_output:
            data["is_chat_output"] = True
        return data

    @staticmethod
    def deserialize(data: dict):
        """Deserialize the flow output definition from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow output definition constructed from the dict.
        :rtype: ~promptflow.contracts.flow.FlowOutputDefinition
        """
        return FlowOutputDefinition(
            ValueType(data["type"]),
            InputAssignment.deserialize(data.get("reference", "")),
            data.get("description", ""),
            data.get("evaluation_only", False),
            data.get("is_chat_output", False),
        )


@dataclass
class FlowInitDefinition(FlowParamDefinitionBase):
    """This class represents the definition of a callable class flow's init kwargs."""

    @staticmethod
    def deserialize(data: dict) -> "FlowInitDefinition":
        """Deserialize the flow init definition from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow input definition constructed from the dict.
        :rtype: ~promptflow.contracts.flow.FlowInitDefinition
        """
        from promptflow.core._model_configuration import MODEL_CONFIG_NAME_2_CLASS

        # support connection & model config type
        def _get_type(data_type: str):
            if ConnectionType.is_connection_class_name(data_type):
                return data_type
            elif data_type in MODEL_CONFIG_NAME_2_CLASS:
                return data_type
            return ValueType(data_type)

        return FlowInitDefinition(
            type=_get_type(data["type"]),
            default=data.get("default", None),
            description=data.get("description", ""),
        )


@dataclass
class NodeVariant:
    """This class represents a node variant.

    :param node: The node of the node variant.
    :type node: ~promptflow.contracts.flow.Node
    :param description: The description of the node variant.
    :type description: str
    """

    node: Node
    description: str = ""

    @staticmethod
    def deserialize(data: dict) -> "NodeVariant":
        """Deserialize the node variant from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The node variant constructed from the dict.
        :rtype: ~promptflow.contracts.flow.NodeVariant
        """
        return NodeVariant(
            Node.deserialize(data["node"]),
            data.get("description", ""),
        )


@dataclass
class NodeVariants:
    """This class represents the variants of a node.

    :param default_variant_id: The default variant id of the node.
    :type default_variant_id: str
    :param variants: The variants of the node.
    :type variants: Dict[str, NodeVariant]
    """

    default_variant_id: str  # The default variant id of the node
    variants: Dict[str, NodeVariant]  # The variants of the node

    @staticmethod
    def deserialize(data: dict) -> "NodeVariants":
        """Deserialize the node variants from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The node variants constructed from the dict.
        :rtype: ~promptflow.contracts.flow.NodeVariants
        """
        variants = {}
        for variant_id, node in data["variants"].items():
            variants[variant_id] = NodeVariant.deserialize(node)
        return NodeVariants(default_variant_id=data.get("default_variant_id", ""), variants=variants)


@dataclass
class FlowBase:
    """This is base class of flow.

    :param id: The id of the flow.
    :type id: str
    :param name: The name of the flow.
    :type name: str
    :param inputs: The inputs of the flow.
    :type inputs: Dict[str, FlowInputDefinition]
    :param outputs: The outputs of the flow.
    :type outputs: Dict[str, FlowOutputDefinition]
    """

    id: str
    name: str
    inputs: Dict[str, FlowInputDefinition]
    outputs: Dict[str, FlowOutputDefinition]

    def get_environment_variables_with_overrides(
        self, environment_variables_overrides: Dict[str, str] = None
    ) -> Dict[str, str]:
        environment_variables = {
            k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in self.environment_variables.items()
        }
        if environment_variables_overrides is not None:
            for k, v in environment_variables_overrides.items():
                environment_variables[k] = v
        return environment_variables

    def get_connection_names(self, environment_variables_overrides: Dict[str, str] = None):
        """Return connection names with environment variables overrides.
        Note: only environment variables exist in flow.environment_variables will be considered.

        :param environment_variables_overrides: used to override flow's environment variables.
        :return: connection names used in this flow.
        """
        environment_variables_overrides = environment_variables_overrides or {}
        connection_names = set({})
        # Add connection names from environment variable reference
        if self.environment_variables:
            for k, v in self.environment_variables.items():
                if k in environment_variables_overrides:
                    # Apply environment variables overrides
                    v = environment_variables_overrides[k]
                if not isinstance(v, str) or not v.startswith("${"):
                    continue
                connection_name, _ = _match_reference(v)
                connection_names.add(connection_name)
        return connection_names


@dataclass
class Flow(FlowBase):
    """This class represents a flow.

    :param id: The id of the flow.
    :type id: str
    :param name: The name of the flow.
    :type name: str
    :param nodes: The nodes of the flow.
    :type nodes: List[Node]
    :param inputs: The inputs of the flow.
    :type inputs: Dict[str, FlowInputDefinition]
    :param outputs: The outputs of the flow.
    :type outputs: Dict[str, FlowOutputDefinition]
    :param tools: The tools of the flow.
    :type tools: List[Tool]
    :param node_variants: The node variants of the flow.
    :type node_variants: Dict[str, NodeVariants]
    :param program_language: The program language of the flow.
    :type program_language: str
    :param environment_variables: The default environment variables of the flow.
    :type environment_variables: Dict[str, object]
    :param message_format: The message format type of the flow to represent different multimedia contracts.
    :type message_format: str
    """

    nodes: List[Node]
    tools: List[Tool]
    node_variants: Dict[str, NodeVariants] = None
    program_language: str = FlowLanguage.Python
    environment_variables: Dict[str, object] = None
    message_format: str = MessageFormatType.BASIC

    def serialize(self):
        """Serialize the flow to a dict.

        :return: The dict of the flow.
        :rtype: dict
        """
        data = {
            "id": self.id,
            "name": self.name,
            "nodes": [n.serialize() for n in self.nodes],
            "inputs": {name: i.serialize() for name, i in self.inputs.items()},
            "outputs": {name: o.serialize() for name, o in self.outputs.items()},
            "tools": [serialize(t) for t in self.tools],
            "language": self.program_language,
            "message_format": self.message_format,
        }
        return data

    @staticmethod
    def _import_requisites(tools, nodes):
        """This function will import tools/nodes required modules to ensure type exists so flow can be executed."""
        try:
            # Import tool modules to ensure register_builtins & registered_connections executed
            for tool in tools:
                if tool.module:
                    try_import(tool.module, f"Import tool {tool.name!r} module {tool.module!r} failed.")
            # Import node provider to ensure register_apis executed so that provider & connection exists.
            for node in nodes:
                if node.module:
                    try_import(node.module, f"Import node {node.name!r} provider module {node.module!r} failed.")
        except Exception as e:
            logger.warning("Failed to import modules...")
            raise FailedToImportModule(
                message=f"Failed to import modules with error: {str(e)}.", target=ErrorTarget.RUNTIME
            ) from e

    @staticmethod
    def deserialize(data: dict) -> "Flow":
        """Deserialize the flow from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow constructed from the dict.
        :rtype: ~promptflow.contracts.flow.Flow
        """
        tools = [Tool.deserialize(t) for t in data.get("tools") or []]
        nodes = [Node.deserialize(n) for n in data.get("nodes") or []]
        Flow._import_requisites(tools, nodes)
        inputs = data.get("inputs") or {}
        outputs = data.get("outputs") or {}
        return Flow(
            # TODO: Remove this fallback.
            id=data.get("id", "default_flow_id"),
            name=data.get("name", "default_flow"),
            nodes=nodes,
            inputs={name: FlowInputDefinition.deserialize(i) for name, i in inputs.items()},
            outputs={name: FlowOutputDefinition.deserialize(o) for name, o in outputs.items()},
            tools=tools,
            node_variants={name: NodeVariants.deserialize(v) for name, v in (data.get("node_variants") or {}).items()},
            program_language=data.get(LANGUAGE_KEY, FlowLanguage.Python),
            environment_variables=data.get("environment_variables") or {},
            message_format=data.get("message_format", MessageFormatType.BASIC),
        )

    def _apply_default_node_variants(self: "Flow"):
        self.nodes = [
            self._apply_default_node_variant(node, self.node_variants) if node.use_variants else node
            for node in self.nodes
        ]
        return self

    @staticmethod
    def _apply_default_node_variant(node: Node, node_variants: Dict[str, NodeVariants]) -> Node:
        if not node_variants:
            return node
        node_variant = node_variants.get(node.name)
        if not node_variant:
            return node
        default_variant = node_variant.variants.get(node_variant.default_variant_id)
        if not default_variant:
            return node
        default_variant.node.name = node.name
        return default_variant.node

    @classmethod
    def _resolve_working_dir(cls, flow_file: Path, working_dir=None) -> Path:
        working_dir = cls._parse_working_dir(flow_file, working_dir)
        cls._update_working_dir(working_dir)
        return working_dir

    @classmethod
    def _parse_working_dir(cls, flow_file: Path, working_dir=None) -> Path:
        if working_dir is None:
            working_dir = Path(flow_file).resolve().parent
        working_dir = Path(working_dir).absolute()
        return working_dir

    @classmethod
    def _update_working_dir(cls, working_dir: Path):
        sys.path.insert(0, str(working_dir))

    @classmethod
    def from_yaml(cls, flow_file: Path, working_dir=None, name=None) -> "Flow":
        """Load flow from yaml file."""
        working_dir = cls._parse_working_dir(flow_file, working_dir)
        with open(working_dir / flow_file, "r", encoding=DEFAULT_ENCODING) as fin:
            flow_data = load_yaml(fin)
        # Name priority: name from payload > name from yaml content > working_dir.stem
        # For portal created flow, there is a meaningless predefined name in yaml, use name from payload to override it.
        return Flow._from_dict(flow_data=flow_data, working_dir=working_dir, name=name)

    @classmethod
    def _from_dict(cls, flow_data: dict, working_dir: Path, name=None) -> "Flow":
        """Load flow from dict."""
        cls._update_working_dir(working_dir)
        if name is None:
            name = flow_data.get("name", _sanitize_python_variable_name(working_dir.stem))
        flow_data["name"] = name
        flow = Flow.deserialize(flow_data)
        flow._set_tool_loader(working_dir)
        return flow

    @classmethod
    def load_env_variables(
        cls, flow_file: Path, working_dir=None, environment_variables_overrides: Dict[str, str] = None
    ) -> Dict[str, str]:
        """
        Read flow_environment_variables from flow yaml.
        If environment_variables_overrides exists, override yaml level configuration.
        Returns the merged environment variables dict.
        """
        if Path(flow_file).suffix.lower() != ".yaml":
            # The flow_file type of eager flow is .py
            return environment_variables_overrides or {}
        working_dir = cls._parse_working_dir(flow_file, working_dir)
        with open(working_dir / flow_file, "r", encoding=DEFAULT_ENCODING) as fin:
            flow_dag = load_yaml(fin)
        flow = Flow.deserialize(flow_dag)
        return flow.get_environment_variables_with_overrides(
            environment_variables_overrides=environment_variables_overrides
        )

    @staticmethod
    def load_message_format_from_yaml(flow_file: Path, working_dir=None) -> str:
        if flow_file and Path(flow_file).suffix.lower() in [".yaml", ".yml"]:
            flow_file = working_dir / flow_file if working_dir else flow_file
            with open(flow_file, "r", encoding="utf-8") as fin:
                flow_dag = load_yaml(fin)
            return flow_dag.get("message_format", MessageFormatType.BASIC)
        return MessageFormatType.BASIC

    def _set_tool_loader(self, working_dir):
        package_tool_keys = [node.source.tool for node in self.nodes if node.source and node.source.tool]
        from promptflow._core.tools_manager import ToolLoader

        # TODO: consider refactor this. It will raise an error if promptflow-tools
        #  is not installed even for csharp flow.
        self._tool_loader = ToolLoader(working_dir, package_tool_keys)

    def _apply_node_overrides(self, node_overrides):
        """Apply node overrides to update the nodes in the flow.

        Example:
            node_overrides = {
                "llm_node1.connection": "some_connection",
                "python_node1.some_key": "some_value",
            }
        We will update the connection field of llm_node1 and the input value of python_node1.some_key.
        """
        if not node_overrides:
            return self
        # We don't do detailed error handling here, since it should never fail
        for key, value in node_overrides.items():
            node_name, input_name = key.split(".")
            node = self.get_node(node_name)
            if node is None:
                raise ValueError(f"Cannot find node {node_name} in flow {self.name}")
            # For LLM node, here we override the connection field in node
            if node.connection and input_name == "connection":
                node.connection = value
            # Other scenarios we override the input value of the inputs
            else:
                node.inputs[input_name] = InputAssignment(value=value)
        return self

    def has_aggregation_node(self):
        """Return whether the flow has aggregation node."""
        return any(n.aggregation for n in self.nodes)

    def get_node(self, node_name):
        """Return the node with the given name."""
        return next((n for n in self.nodes if n.name == node_name), None)

    def get_tool(self, tool_name):
        """Return the tool with the given name."""
        return next((t for t in self.tools if t.name == tool_name), None)

    def is_reduce_node(self, node_name):
        """Return whether the node is a reduce node."""
        node = next((n for n in self.nodes if n.name == node_name), None)
        return node is not None and node.aggregation

    def is_normal_node(self, node_name):
        """Return whether the node is a normal node."""
        node = next((n for n in self.nodes if n.name == node_name), None)
        return node is not None and not node.aggregation

    def is_llm_node(self, node):
        """Given a node, return whether it uses LLM tool."""
        return node.type == ToolType.LLM

    def is_referenced_by_flow_output(self, node):
        """Given a node, return whether it is referenced by output."""
        return any(
            output
            for output in self.outputs.values()
            if all(
                (
                    output.reference.value_type == InputValueType.NODE_REFERENCE,
                    output.reference.value == node.name,
                )
            )
        )

    def is_node_referenced_by(self, node: Node, other_node: Node):
        """Given two nodes, return whether the first node is referenced by the second node."""
        return other_node.inputs and any(
            input
            for input in other_node.inputs.values()
            if input.value_type == InputValueType.NODE_REFERENCE and input.value == node.name
        )

    def is_referenced_by_other_node(self, node):
        """Given a node, return whether it is referenced by other node."""
        return any(flow_node for flow_node in self.nodes if self.is_node_referenced_by(node, flow_node))

    def is_chat_flow(self):
        """Return whether the flow is a chat flow."""
        chat_input_name = self.get_chat_input_name()
        return chat_input_name is not None

    def get_chat_input_name(self):
        """Return the name of the chat input."""
        return next((name for name, i in self.inputs.items() if i.is_chat_input), None)

    def get_chat_output_name(self):
        """Return the name of the chat output."""
        return next((name for name, o in self.outputs.items() if o.is_chat_output), None)

    def _get_connection_name_from_tool(self, tool: Tool, node: Node):
        connection_names = {}
        value_types = set({v.value for v in ValueType.__members__.values()})
        for k, v in tool.inputs.items():
            input_type = [typ.value if isinstance(typ, Enum) else typ for typ in v.type]
            if all(typ.lower() in value_types for typ in input_type):
                # All type is value type, the key is not a possible connection key.
                continue
            input_assignment = node.inputs.get(k)
            # Add literal node assignment values to results, skip node reference
            if isinstance(input_assignment, InputAssignment) and input_assignment.value_type == InputValueType.LITERAL:
                connection_names[k] = input_assignment.value
        return connection_names

    @classmethod
    def _get_connection_inputs_from_tool(cls, tool: Tool) -> list:
        """Return tool's connection inputs."""
        connection_inputs = []
        for k, v in tool.inputs.items():
            input_type = [typ.value if isinstance(typ, Enum) else typ for typ in v.type]
            if all(ConnectionType.is_connection_class_name(t) for t in input_type):
                connection_inputs.append(k)
        return connection_inputs

    def get_connection_names(self, environment_variables_overrides: Dict[str, str] = None):
        """Return connection names."""
        connection_names = super().get_connection_names(environment_variables_overrides=environment_variables_overrides)
        nodes = [
            self._apply_default_node_variant(node, self.node_variants) if node.use_variants else node
            for node in self.nodes
        ]
        for node in nodes:
            if node.connection:
                connection_names.add(node.connection)
                continue
            if node.type == ToolType.PROMPT or node.type == ToolType.LLM:
                continue
            logger.debug(f"Try loading connection names for node {node.name}.")
            tool = self.get_tool(node.tool) or self._tool_loader.load_tool_for_node(node)
            if tool:
                node_connection_names = list(self._get_connection_name_from_tool(tool, node).values())
            else:
                node_connection_names = []
            if node_connection_names:
                logger.debug(f"Connection names of node {node.name}: {node_connection_names}")
            else:
                logger.debug(f"Node {node.name} doesn't reference any connection.")
            connection_names.update(node_connection_names)

        return set({item for item in connection_names if item})

    def get_connection_input_names_for_node(self, node_name):
        """Return connection input names for a node, will also return node connection inputs without assignment.

        :param node_name: node name
        """

        node = self.get_node(node_name)
        if node and node.use_variants:
            node = self._apply_default_node_variant(node, self.node_variants)
        # Ignore Prompt node and LLM node, due to they do not have connection inputs.
        if not node or node.type == ToolType.PROMPT or node.type == ToolType.LLM:
            return []
        tool = self.get_tool(node.tool) or self._tool_loader.load_tool_for_node(node)
        if tool:
            return self._get_connection_inputs_from_tool(tool)
        return []

    def _replace_with_variant(self, variant_node: Node, variant_tools: list):
        for index, node in enumerate(self.nodes):
            if node.name == variant_node.name:
                self.nodes[index] = variant_node
                break
        self.tools = self.tools + variant_tools


@dataclass
class FlexFlow(FlowBase):
    """This class represents a flex flow.

    :param id: The id of the flow.
    :type id: str
    :param name: The name of the flow.
    :type name: str
    :param inputs: The inputs of the flow.
    :type inputs: Dict[str, FlowInputDefinition]
    :param outputs: The outputs of the flow.
    :type outputs: Dict[str, FlowOutputDefinition]
    :param program_language: The program language of the flow.
    :type program_language: str
    :param environment_variables: The default environment variables of the flow.
    :type environment_variables: Dict[str, object]
    :param message_format: The message format type of the flow to represent different multimedia contracts.
    :type message_format: str
    :param sample: Sample data for the flow. Will become default inputs & init kwargs if not provided.
    :type sample: Dict[str, object]
    """

    init: Dict[str, FlowInputDefinition] = None
    program_language: str = FlowLanguage.Python
    environment_variables: Dict[str, object] = None
    # eager flow does not support multimedia contract currently, it is set to basic by default.
    message_format: str = MessageFormatType.BASIC
    sample: Dict[str, dict] = None

    @staticmethod
    def deserialize(data: dict) -> "FlexFlow":
        """Deserialize the flow from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow constructed from the dict.
        :rtype: ~promptflow.contracts.flow.EagerFlow
        """

        inputs = data.get("inputs") or {}
        outputs = data.get("outputs") or {}
        init = data.get("init") or {}
        return FlexFlow(
            id=data.get("id", "default_flow_id"),
            name=data.get("name", "default_flow"),
            inputs={name: FlowInputDefinition.deserialize(i) for name, i in inputs.items()},
            outputs={name: FlowOutputDefinition.deserialize(o) for name, o in outputs.items()},
            init={name: FlowInitDefinition.deserialize(i) for name, i in init.items()},
            program_language=data.get(LANGUAGE_KEY, FlowLanguage.Python),
            environment_variables=data.get("environment_variables") or {},
            sample=data.get("sample") or {},
        )

    @classmethod
    def _from_dict(cls, flow_data: dict, working_dir: Path, name=None) -> "FlexFlow":
        """Load flow from dict."""
        from promptflow._core.entry_meta_generator import generate_flow_meta

        from .._utils.flow_utils import resolve_python_entry_file

        Flow._update_working_dir(working_dir)
        if name is None:
            name = flow_data.get("name", _sanitize_python_variable_name(working_dir.stem))
        flow_data["name"] = name

        entry = flow_data.get("entry")
        entry_file = resolve_python_entry_file(entry=entry, working_dir=working_dir)

        meta_dict = generate_flow_meta(
            flow_directory=working_dir,
            source_path=entry_file,
            data=flow_data,
        )
        return cls.deserialize(meta_dict)

    def get_connection_names(self, environment_variables_overrides: Dict[str, str] = None):
        """Return connection names."""
        connection_names = super().get_connection_names(environment_variables_overrides=environment_variables_overrides)

        return set({item for item in connection_names if item})


@dataclass
class PromptyFlow(FlowBase):
    """This class represents a prompty flow.

    :param id: The id of the flow.
    :type id: str
    :param name: The name of the flow.
    :type name: str
    :param inputs: The inputs of the flow.
    :type inputs: Dict[str, FlowInputDefinition]
    :param outputs: The outputs of the flow.
    :type outputs: Dict[str, FlowOutputDefinition]
    :param program_language: The program language of the flow.
    :type program_language: str
    :param environment_variables: The default environment variables of the flow.
    :type environment_variables: Dict[str, object]
    :param message_format: The message format type of the flow to represent different multimedia contracts.
    :type message_format: str
    """

    program_language: str = FlowLanguage.Python
    environment_variables: Dict[str, object] = None
    message_format: str = MessageFormatType.BASIC

    @classmethod
    def deserialize(cls, data: dict) -> "PromptyFlow":
        """Deserialize the prompty flow from a dict.

        :param data: The dict to be deserialized.
        :type data: dict
        :return: The flow constructed from the dict.
        :rtype: ~promptflow.contracts.flow.PromptyFlow
        """
        inputs = data.get("inputs") or {}
        outputs = data.get("outputs") or {}
        return PromptyFlow(
            id=data.get("id", "default_flow_id"),
            name=data.get("name", "default_flow"),
            inputs={name: FlowInputDefinition.deserialize(i) for name, i in inputs.items()},
            outputs={name: FlowOutputDefinition.deserialize(o) for name, o in outputs.items()},
            program_language=data.get(LANGUAGE_KEY, FlowLanguage.Python),
            environment_variables=data.get("environment_variables") or {},
            message_format=data.get("message_format", MessageFormatType.BASIC),
        )

    @classmethod
    def _from_dict(cls, flow_data: dict, working_dir: Path, name=None) -> "PromptyFlow":
        """Load flow from dict."""
        Flow._update_working_dir(working_dir)
        if name is None:
            name = flow_data.get("name", _sanitize_python_variable_name(working_dir.stem))
        flow_data["name"] = name

        return cls.deserialize(flow_data)

    def get_connection_names(self, environment_variables_overrides: Dict[str, str] = None):
        """Return connection names."""
        connection_names = super().get_connection_names(environment_variables_overrides=environment_variables_overrides)

        return set({item for item in connection_names if item})
