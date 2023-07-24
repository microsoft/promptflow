import copy
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from ..utils.dataclass_serializer import serialize
from ..utils.utils import try_import
from .tool import ConnectionType, Tool, ToolType, ValueType


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
    reduce: bool = False
    enable_cache: bool = False
    source: Optional[ToolSource] = None
    type: Optional[ToolType] = None
    skip: Optional[SkipCondition] = None

    def serialize(self):
        data = asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v})
        self.inputs = self.inputs or {}
        data.update({"inputs": {name: i.serialize() for name, i in self.inputs.items()}})
        if self.reduce:
            data["reduce"] = True
        return data

    @staticmethod
    def deserialize(data: dict) -> "Node":
        node = Node(
            name=data["name"],
            tool=data.get("tool"),
            inputs={name: InputAssignment.deserialize(v) for name, v in (data.get("inputs") or {}).items()},
            comment=data.get("comment", ""),
            api=data.get("api", None),
            provider=data.get("provider", None),
            module=data.get("module", None),
            connection=data.get("connection", None),
            # TODO: Rename reduce to aggregation
            reduce=data.get("reduce", False) or data.get("aggregation", False),
            enable_cache=data.get("enable_cache", False),
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
        return data

    @staticmethod
    def deserialize(data: dict) -> "FlowInputDefinition":
        return FlowInputDefinition(
            ValueType(data["type"]),
            data.get("default", None),
            data.get("description", ""),
            data.get("enum", []),
            data.get("is_chat_input", False),
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
class Flow:
    id: str
    name: str
    nodes: List[Node]
    inputs: Dict[str, FlowInputDefinition]
    outputs: Dict[str, FlowOutputDefinition]
    tools: List[Tool]

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
    def import_requisites(tools, nodes):
        """This function will import tools/nodes required modules to ensure type exists so flow can be executed."""
        # Import tool modules to ensure register_builtins & registered_connections executed
        for tool in tools:
            if tool.module:
                try_import(tool.module, f"Import tool {tool.name!r} module {tool.module!r} failed.")
        # Import node provider to ensure register_apis executed so that provider & connection exists.
        for node in nodes:
            if node.module:
                try_import(node.module, f"Import node {node.name!r} provider module {node.module!r} failed.")

    @staticmethod
    def deserialize(data: dict) -> "Flow":
        tools = [Tool.deserialize(t) for t in data.get("tools", [])]
        nodes = [Node.deserialize(n) for n in data.get("nodes", [])]
        Flow.import_requisites(tools, nodes)
        return Flow(
            # TODO: Remove this fallback.
            data.get("id", data.get("name", "default_flow_id")),
            data.get("name", "default_flow"),
            nodes,
            {name: FlowInputDefinition.deserialize(i) for name, i in data.get("inputs", {}).items()},
            {name: FlowOutputDefinition.deserialize(o) for name, o in data.get("outputs", {}).items()},
            tools=tools,
        )

    @staticmethod
    def from_yaml(flow_file: Path, working_dir=None) -> "Flow":
        """Load flow from yaml file."""
        if working_dir is None:
            working_dir = Path(flow_file).resolve().parent
        working_dir = Path(working_dir).absolute()
        sys.path.insert(0, str(working_dir))
        with open(working_dir / flow_file, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        from promptflow.core.tools_manager import gen_tool_by_source

        for node in flow.nodes:
            if node.source:
                tool = gen_tool_by_source(node.name, node.source, node.type, working_dir)
                node.tool = tool.name
                flow.tools.append(tool)
        return flow

    def has_aggregation_node(self):
        return any(n.reduce for n in self.nodes)

    def get_node(self, node_name):
        return next((n for n in self.nodes if n.name == node_name), None)

    def get_tool(self, tool_name):
        return next((t for t in self.tools if t.name == tool_name), None)

    def is_reduce_node(self, node_name):
        node = next((n for n in self.nodes if n.name == node_name), None)
        return node is not None and node.reduce

    def is_normal_node(self, node_name):
        node = next((n for n in self.nodes if n.name == node_name), None)
        return node is not None and not node.reduce

    def is_llm_node(self, node):
        """Given a node, return whether it uses LLM tool."""
        tool = self.get_tool(node.tool)
        return tool and tool.type == ToolType.LLM

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

    def replace_with_variant(self, variant_node: Node, variant_tools: list):
        for index, node in enumerate(self.nodes):
            if node.name == variant_node.name:
                self.nodes[index] = variant_node
                break
        self.tools = self.tools + variant_tools


@dataclass
class BaseFlowRequest:
    flow: Optional[Flow]
    connections: Dict[str, Dict[str, str]]


BASELINE_VARIANT_ID = "variant0"


@dataclass
class BatchFlowRequest(BaseFlowRequest):
    batch_inputs: List[Dict[str, Any]]
    name: str = ""
    description: str = ""
    tags: Mapping[str, str] = None

    baseline_variant_id: str = ""
    variants: Dict[str, List[Node]] = None
    variants_tools: List[Tool] = None
    variants_codes: Dict[str, str] = None
    variants_runs: Dict[str, str] = None

    bulk_test_id: Optional[str] = None

    eval_flow: Optional[Flow] = None
    eval_flow_run_id: Optional[str] = None
    eval_flow_inputs_mapping: Optional[Mapping[str, str]] = None

    @staticmethod
    def deserialize(data: dict) -> "BatchFlowRequest":
        return BatchFlowRequest(
            flow=Flow.deserialize(data["flow"]) if "flow" in data else None,
            connections=data.get("connections", {}),
            batch_inputs=data.get("batch_inputs", []),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tags=data.get("tags", {}),
            baseline_variant_id=data.get("baseline_variant_id", ""),
            variants={
                variant_id: [Node.deserialize(node) for node in nodes]
                for variant_id, nodes in data.get("variants", {}).items()
            },
            variants_tools=[Tool.deserialize(t) for t in data.get("variants_tools", [])],
            variants_runs=data.get("variants_runs", {}),
            variants_codes=data.get("variants_codes", {}),
            bulk_test_id=data.get("bulk_test_id", None),
            eval_flow=Flow.deserialize(data["eval_flow"]) if data.get("eval_flow", None) else None,
            eval_flow_run_id=data.get("eval_flow_run_id"),
            eval_flow_inputs_mapping=data.get("eval_flow_inputs_mapping", {}),
        )


@dataclass
class NodesRequest(BaseFlowRequest):
    node_name: str
    node_inputs: Dict[str, Any]
    variants: Dict[str, List[Node]] = None
    variants_tools: List[Tool] = None
    variants_codes: Dict[str, str] = None

    @staticmethod
    def deserialize(data: dict) -> "NodesRequest":
        return NodesRequest(
            Flow.deserialize(data["flow"]) if "flow" in data else None,
            data.get("connections", {}),
            data["node_name"],
            data["node_inputs"],
            variants={
                variant_id: [Node.deserialize(node) for node in nodes]
                for variant_id, nodes in data.get("variants", {}).items()
            },
            variants_tools=[Tool.deserialize(t) for t in data.get("variants_tools", [])],
            variants_codes=data.get("variants_codes", {}),
        )

    @staticmethod
    def get_node_name_from_node_inputs_key(k: str) -> str:
        """
        Node input keys might have the format: {node name}.output
        Strip .output and return node name in this case.
        """
        if k.endswith(".output"):
            return k[: -len(".output")]
        return k

    def get_node_connection_names(self, run_mode):
        # Get the connection name from node_input(Python) and connection field(LLM) for current node.
        node = next((n for n in self.flow.nodes if n.name == self.node_name), None)
        if node is None:
            raise ValueError(f"Node name {self.node_name} not found in flow nodes.")
        # Create a new flow, leave node to execute only and update the inputs.
        new_flow = copy.deepcopy(self.flow)
        node_idx, node = next(
            ((_idx, n) for _idx, n in enumerate(new_flow.nodes) if n.name == self.node_name), (None, None)
        )
        from .run_mode import RunMode

        # If run_mode is SingleNode, only keep the node to execute, if is FromNode then nodes after it.
        if run_mode == RunMode.SingleNode:
            new_flow.nodes = [node]
        elif run_mode == RunMode.FromNode:
            new_flow.nodes = new_flow.nodes[node_idx:]
        else:
            raise NotImplementedError(f"Run mode {run_mode} is not supported in current version.")
        return new_flow.get_connection_names()


@dataclass
class EvalRequest(BaseFlowRequest):
    bulk_test_inputs: List[Mapping[str, Any]]
    bulk_test_flow_run_ids: List[str]
    bulk_test_flow_id: str
    bulk_test_id: str
    inputs_mapping: Optional[Mapping[str, str]] = None

    @staticmethod
    def deserialize(data: dict) -> "EvalRequest":
        return EvalRequest(
            Flow.deserialize(data["flow"]) if "flow" in data else None,
            connections=data.get("connections", {}),
            bulk_test_inputs=data.get("bulk_test_inputs", []),
            bulk_test_flow_run_ids=data["bulk_test_flow_run_ids"],
            bulk_test_flow_id=data["bulk_test_flow_id"],
            bulk_test_id=data["bulk_test_id"],
            inputs_mapping=data.get("inputs_mapping"),
        )
