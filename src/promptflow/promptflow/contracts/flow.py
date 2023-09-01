# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from promptflow.exceptions import ErrorTarget

from .._utils.dataclass_serializer import serialize
from .._utils.utils import try_import
from ._errors import FailedToImportModule
from .tool import ConnectionType, Tool, ToolType, ValueType

logger = logging.getLogger(__name__)


class InputValueType(Enum):
    LITERAL = "Literal"
    FLOW_INPUT = "FlowInput"
    NODE_REFERENCE = "NodeReference"


FLOW_INPUT_PREFIX = "flow."
FLOW_INPUT_PREFIXES = [FLOW_INPUT_PREFIX, "inputs."]  # Use a list for backward compatibility


@dataclass
class InputAssignment:
    value: Any
    value_type: InputValueType = InputValueType.LITERAL
    section: str = ""
    property: str = ""

    def serialize(self):
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
        """Deserialize the reference(including node/flow reference) part of an input assignment."""
        if FlowInputAssignment.is_flow_input(value):
            return FlowInputAssignment.deserialize(value)
        return InputAssignment.deserialize_node_reference(value)

    @staticmethod
    def deserialize_node_reference(data: str) -> "InputAssignment":
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
    prefix: str = FLOW_INPUT_PREFIX

    @staticmethod
    def is_flow_input(input_value: str) -> bool:
        for prefix in FLOW_INPUT_PREFIXES:
            if input_value.startswith(prefix):
                return True
        return False

    @staticmethod
    def deserialize(value: str) -> "FlowInputAssignment":
        for prefix in FLOW_INPUT_PREFIXES:
            if value.startswith(prefix):
                return FlowInputAssignment(
                    value=value[len(prefix) :], value_type=InputValueType.FLOW_INPUT, prefix=prefix
                )
        raise ValueError(f"Unexpected flow input value {value}")


class ToolSourceType(str, Enum):
    Code = "code"
    Package = "package"
    PackageWithPrompt = "package_with_prompt"


@dataclass
class ToolSource:
    type: ToolSourceType = ToolSourceType.Code
    tool: Optional[str] = None
    path: Optional[str] = None

    @staticmethod
    def deserialize(data: dict) -> "ToolSource":
        result = ToolSource(data.get("type", ToolSourceType.Code.value))
        if "tool" in data:
            result.tool = data["tool"]
        if "path" in data:
            result.path = data["path"]
        return result


@dataclass
class SkipCondition:
    condition: InputAssignment
    condition_value: Any
    return_value: InputAssignment

    @staticmethod
    def deserialize(data: dict) -> "SkipCondition":
        result = SkipCondition(
            condition=InputAssignment.deserialize(data["when"]),
            condition_value=data["is"],
            return_value=InputAssignment.deserialize(data["return"]),
        )
        return result


@dataclass
class Node:
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
    skip: Optional[SkipCondition] = None

    def serialize(self):
        data = asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v})
        self.inputs = self.inputs or {}
        data.update({"inputs": {name: i.serialize() for name, i in self.inputs.items()}})
        if self.aggregation:
            data["aggregation"] = True
            data["reduce"] = True  # TODO: Remove this fallback.
        return data

    @staticmethod
    def deserialize(data: dict) -> "Node":
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
        if "skip" in data:
            node.skip = SkipCondition.deserialize(data["skip"])
        return node


@dataclass
class FlowInputDefinition:
    type: ValueType
    default: str = None
    description: str = None
    enum: List[str] = None
    is_chat_input: bool = False
    is_chat_history: bool = None

    def serialize(self):
        data = {}
        data["type"] = self.type.value
        if self.default:
            data["default"] = str(self.default)
        if self.description:
            data["description"] = self.description
        if self.enum:
            data["enum"] = self.enum
        if self.is_chat_input:
            data["is_chat_input"] = True
        if self.is_chat_history:
            data["is_chat_history"] = True
        return data

    @staticmethod
    def deserialize(data: dict) -> "FlowInputDefinition":
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
    type: ValueType
    reference: InputAssignment
    description: str = ""
    evaluation_only: bool = False
    is_chat_output: bool = False

    def serialize(self):
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
        return FlowOutputDefinition(
            ValueType(data["type"]),
            InputAssignment.deserialize(data.get("reference", "")),
            data.get("description", ""),
            data.get("evaluation_only", False),
            data.get("is_chat_output", False),
        )


@dataclass
class NodeVariant:
    node: Node
    description: str = ""

    @staticmethod
    def deserialize(data: dict) -> "NodeVariant":
        return NodeVariant(
            Node.deserialize(data["node"]),
            data.get("description", ""),
        )


@dataclass
class NodeVariants:
    default_variant_id: str  # The default variant id of the node
    variants: Dict[str, NodeVariant]  # The variants of the node

    @staticmethod
    def deserialize(data: dict) -> "NodeVariants":
        variants = {}
        for variant_id, node in data["variants"].items():
            variants[variant_id] = NodeVariant.deserialize(node)
        return NodeVariants(default_variant_id=data.get("default_variant_id", ""), variants=variants)


@dataclass
class Flow:
    id: str
    name: str
    nodes: List[Node]
    inputs: Dict[str, FlowInputDefinition]
    outputs: Dict[str, FlowOutputDefinition]
    tools: List[Tool]
    node_variants: Dict[str, NodeVariants] = None

    def serialize(self):
        data = {
            "id": self.id,
            "name": self.name,
            "nodes": [n.serialize() for n in self.nodes],
            "inputs": {name: i.serialize() for name, i in self.inputs.items()},
            "outputs": {name: o.serialize() for name, o in self.outputs.items()},
            "tools": [serialize(t) for t in self.tools],
        }
        return data

    @staticmethod
    def _import_requisites(tools, nodes):
        try:
            """This function will import tools/nodes required modules to ensure type exists so flow can be executed."""
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
        tools = [Tool.deserialize(t) for t in data.get("tools") or []]
        nodes = [Node.deserialize(n) for n in data.get("nodes") or []]
        Flow._import_requisites(tools, nodes)
        inputs = data.get("inputs") or {}
        outputs = data.get("outputs") or {}
        return Flow(
            # TODO: Remove this fallback.
            data.get("id", data.get("name", "default_flow_id")),
            data.get("name", "default_flow"),
            nodes,
            {name: FlowInputDefinition.deserialize(i) for name, i in inputs.items()},
            {name: FlowOutputDefinition.deserialize(o) for name, o in outputs.items()},
            tools=tools,
            node_variants={name: NodeVariants.deserialize(v) for name, v in (data.get("node_variants") or {}).items()},
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

    @staticmethod
    def _resolve_working_dir(flow_file: Path, working_dir=None) -> Path:
        if working_dir is None:
            working_dir = Path(flow_file).resolve().parent
        working_dir = Path(working_dir).absolute()
        sys.path.insert(0, str(working_dir))
        return working_dir

    @staticmethod
    def from_yaml(flow_file: Path, working_dir=None, gen_tool=True) -> "Flow":
        """Load flow from yaml file."""
        working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        with open(working_dir / flow_file, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))

        # TODO: Postpone tool generation to flow execution in all scenarios and remove this parameter.
        if not gen_tool:
            return flow
        from promptflow._core.tools_manager import gen_tool_by_source

        for node in flow.nodes:
            if node.source:
                tool = gen_tool_by_source(node.name, node.source, node.type, working_dir)
                node.tool = tool.name
                flow.tools.append(tool)
        return flow

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
        return any(n.aggregation for n in self.nodes)

    def get_node(self, node_name):
        return next((n for n in self.nodes if n.name == node_name), None)

    def get_tool(self, tool_name):
        return next((t for t in self.tools if t.name == tool_name), None)

    def is_reduce_node(self, node_name):
        node = next((n for n in self.nodes if n.name == node_name), None)
        return node is not None and node.aggregation

    def is_normal_node(self, node_name):
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
        chat_input_name = self.get_chat_input_name()
        return chat_input_name is not None

    def get_chat_input_name(self):
        return next((name for name, i in self.inputs.items() if i.is_chat_input), None)

    def get_chat_output_name(self):
        return next((name for name, o in self.outputs.items() if o.is_chat_output), None)

    def get_connection_input_names_for_node(self, node_name):
        """Return connection input names."""
        node = self.get_node(node_name)
        if not node:
            return []
        result = []
        value_types = set({v.value for v in ValueType.__members__.values()})
        tool = self.get_tool(node.tool)
        for k, v in tool.inputs.items():
            input_type = [typ.value if isinstance(typ, Enum) else typ for typ in v.type]
            if all(typ.lower() in value_types for typ in input_type):
                # All type is value type, the key is not a possible connection key.
                continue
            input_assignment = node.inputs.get(k)
            # Add literal node assignment values to results, skip node reference
            if isinstance(input_assignment, InputAssignment) and input_assignment.value_type == InputValueType.LITERAL:
                result.append(k)
        return result

    def get_connection_names(self):
        """Return the possible connection names in flow object."""
        connection_names = set({})
        tool_metas = {tool.name: tool for tool in self.tools}
        value_types = set({v.value for v in ValueType.__members__.values()})
        for node in self.nodes:
            if node.connection:
                # Some node has a separate field for connection.
                connection_names.add(node.connection)
                continue
            # Get tool meta and return possible input name with connection type
            if node.tool not in tool_metas:
                msg = f"Node {node.name!r} references tool {node.tool!r} which is not in the flow {self.name!r}."
                raise Exception(msg)
            tool = tool_metas.get(node.tool)
            # Force regard input type not in ValueType as connection type.
            for k, v in tool.inputs.items():
                input_type = [typ.value if isinstance(typ, Enum) else typ for typ in v.type]
                if all(typ.lower() in value_types for typ in input_type):
                    # All type is value type, the key is not a possible connection key.
                    continue
                input_assignment = node.inputs.get(k)
                # Add literal node assignment values to results, skip node reference
                if (
                    isinstance(input_assignment, InputAssignment)
                    and input_assignment.value_type == InputValueType.LITERAL
                ):
                    connection_names.add(input_assignment.value)
        # Filter None and empty string out
        return set({item for item in connection_names if item})

    def _replace_with_variant(self, variant_node: Node, variant_tools: list):
        for index, node in enumerate(self.nodes):
            if node.name == variant_node.name:
                self.nodes[index] = variant_node
                break
        self.tools = self.tools + variant_tools
