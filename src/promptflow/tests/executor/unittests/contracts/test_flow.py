from pathlib import Path

import pytest
import yaml

from promptflow._sdk.entities._connection import AzureContentSafetyConnection
from promptflow.contracts._errors import FailedToImportModule, NodeConditionConflict
from promptflow.contracts.flow import (
    Flow,
    FlowInputAssignment,
    FlowInputDefinition,
    FlowOutputDefinition,
    InputAssignment,
    InputValueType,
    Node,
)
from promptflow.contracts.tool import ConnectionType, InputDefinition, Tool, ToolType, ValueType
from promptflow.exceptions import UserErrorException

from ...utils import WRONG_FLOW_ROOT, get_flow_package_tool_definition, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


# Is this unittest or e2etest?
@pytest.mark.e2etest
class TestFlowContract:
    @pytest.mark.parametrize(
        "flow_folder, expected_connection_names",
        [
            ("web_classification", {"azure_open_ai_connection"}),
            ("basic-with-connection", {"azure_open_ai_connection"}),
            ("flow_with_dict_input_with_variant", {"mock_custom_connection"}),
        ],
    )
    def test_flow_get_connection_names(self, flow_folder, expected_connection_names):
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        assert flow.get_connection_names() == expected_connection_names

    def test_flow_get_connection_input_names_for_node_with_variants(self):
        # Connection input exists only in python node
        flow_folder = "flow_with_dict_input_with_variant"
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        assert flow.get_connection_input_names_for_node("print_val") == ["conn"]

    def test_flow_get_connection_names_with_package_tool(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        flow_file = flow_folder / "flow.dag.yaml"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tool_definition)
        flow = Flow.from_yaml(flow_file)
        connection_names = flow.get_connection_names()
        assert connection_names == {"azure_open_ai_connection"}

    def test_flow_get_connection_input_names_for_node(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        flow_file = flow_folder / "flow.dag.yaml"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tool_definition)
        flow = Flow.from_yaml(flow_file)
        connection_names = flow.get_connection_input_names_for_node(flow.nodes[0].name)
        assert connection_names == ["connection"]

    def test_node_condition_conflict(self):
        flow_folder = "node_condition_conflict"
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with pytest.raises(NodeConditionConflict) as e:
            with open(flow_yaml, "r") as fin:
                Flow.deserialize(yaml.safe_load(fin))
        error_message = "Node 'test_node' can't have both skip and activate condition."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "flow_folder",
        [
            ("web_classification"),
            ("flow_with_dict_input_with_variant"),
        ],
    )
    def test_flow_serialize(self, flow_folder):
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        serialized_flow = flow.serialize()
        assert serialized_flow["name"] == flow.name
        assert serialized_flow["nodes"] == [n.serialize() for n in flow.nodes]
        assert serialized_flow["inputs"] == {name: i.serialize() for name, i in flow.inputs.items()}
        assert serialized_flow["tools"] == [t.serialize() for t in flow.tools]

        deserialize_flow = Flow.deserialize(serialized_flow)
        assert deserialize_flow.name == flow.name
        assert len(deserialize_flow.nodes) == len(flow.nodes)
        assert deserialize_flow.inputs == flow.inputs
        assert deserialize_flow.outputs == flow.outputs
        assert deserialize_flow.tools == flow.tools

    def test_import_requisites(self):
        tool1 = Tool(name="tool1", type=ToolType.PYTHON, inputs={"name": InputDefinition(type=["int"])}, module="yaml")
        tool2 = Tool(
            name="tool2", type=ToolType.PYTHON, inputs={"name": InputDefinition(type=["int"])}, module="module"
        )
        node1 = Node(
            name="node1", tool="tool1", inputs={"name": InputAssignment("value", InputValueType.LITERAL)}, module="yaml"
        )
        node2 = Node(
            name="node2",
            tool="tool2",
            inputs={"name": InputAssignment("value", InputValueType.LITERAL)},
            module="module",
        )
        tools = [tool1, tool2]
        nodes = [node1, node2]

        with pytest.raises(FailedToImportModule) as e:
            Flow._import_requisites(tools, nodes)

        assert str(e.value).startswith("Failed to import modules with error:")

    def test_apply_default_node_variants(self):
        flow_folder = "flow_with_dict_input_with_variant"
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        # test when node.use_variants is True
        flow._apply_default_node_variants()
        assert flow.nodes[0].use_variants is False
        assert flow.nodes[0].inputs == flow.node_variants["print_val"].variants["variant1"].node.inputs
        # test when node.use_variants is False
        flow = Flow.from_yaml(flow_yaml)
        flow.nodes[0].use_variants = False
        tmp_nodes = flow.nodes
        flow._apply_default_node_variants()
        assert flow.nodes == tmp_nodes

    def test_apply_default_node_variant(self):
        flow_folder = "flow_with_dict_input_with_variant"
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        node = flow.nodes[0]
        variant = flow.node_variants
        # test when node_variants is None
        assert Flow._apply_default_node_variant(node, {}) == node
        # test when node.name is not in node_variants
        variant_change_nodename = variant.copy()
        variant_change_nodename["test"] = variant_change_nodename.pop("print_val")
        assert Flow._apply_default_node_variant(node, variant_change_nodename) == node
        # test when default_variant_id is not in variants
        variant_change_id = variant.copy()
        variant_change_id["print_val"].default_variant_id = "test"
        assert Flow._apply_default_node_variant(node, variant_change_id) == node

    def test_apply_node_overrides(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert flow == flow._apply_node_overrides(None)
        assert flow == flow._apply_node_overrides({})

        node_overrides = {
            "llm_node1.connection": "some_connection",
        }
        with pytest.raises(ValueError):
            flow._apply_node_overrides(node_overrides)

        node_overrides = {
            "classify_with_llm.connection": "custom_connection",
            "fetch_text_content_from_url.test": "test",
        }
        flow = flow._apply_node_overrides(node_overrides)
        assert flow.nodes[3].connection == "custom_connection"
        assert flow.nodes[0].inputs["test"].value == "test"

    def test_has_aggregation_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.has_aggregation_node()
        flow.nodes[0].aggregation = True
        assert flow.has_aggregation_node()

    def test_is_reduce_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_reduce_node("test")
        assert not flow.is_reduce_node("fetch_text_content_from_url")
        flow.nodes[0].aggregation = True
        assert flow.is_reduce_node("fetch_text_content_from_url")

    def test_is_normal_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_normal_node("test")
        assert flow.is_normal_node("fetch_text_content_from_url")
        flow.nodes[0].aggregation = True
        assert not flow.is_normal_node("fetch_text_content_from_url")

    def test_is_llm_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert flow.is_llm_node(flow.nodes[3])
        assert not flow.is_llm_node(flow.nodes[0])

    def test_is_referenced_by_flow_output(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_referenced_by_flow_output(flow.nodes[0])
        assert flow.is_referenced_by_flow_output(flow.nodes[4])

    def test_is_node_referenced_by(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_node_referenced_by(flow.nodes[3], flow.nodes[2])
        assert flow.is_node_referenced_by(flow.nodes[2], flow.nodes[3])

    def test_is_referenced_by_other_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_referenced_by_other_node(flow.nodes[0])
        assert flow.is_referenced_by_other_node(flow.nodes[2])

    def test_is_chat_flow(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert not flow.is_chat_flow()
        flow = Flow.from_yaml(get_yaml_file("chat_flow"))
        assert flow.is_chat_flow()

    def test_get_chat_input_name(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert flow.get_chat_input_name() is None
        flow = Flow.from_yaml(get_yaml_file("chat_flow"))
        assert flow.get_chat_input_name() == "question"

    def test_get_chat_output_name(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert flow.get_chat_output_name() is None
        flow = Flow.from_yaml(get_yaml_file("chat_flow"))
        assert flow.get_chat_output_name() == "answer"

    def test_get_connection_input_names_for_node(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        assert flow.get_connection_input_names_for_node("fetch_text_content_from_url") == []
        assert flow.get_connection_input_names_for_node("classify_with_llm") == []
        assert flow.get_connection_input_names_for_node("prepare_examples") == []
        flow.nodes[0].source = None
        with pytest.raises(UserErrorException):
            flow.get_connection_input_names_for_node("fetch_text_content_from_url")

        flow = Flow.from_yaml(get_yaml_file("custom_connection_flow"))
        assert flow.get_connection_input_names_for_node("print_env") == ["connection"]

    def test_replace_with_variant(self):
        flow = Flow.from_yaml(get_yaml_file("web_classification"))
        tool_cnt = len(flow.tools)
        flow._replace_with_variant(flow.nodes[0], [flow.nodes[1].tool, flow.nodes[2].tool])
        assert len(flow.tools) == tool_cnt + 2


@pytest.mark.unittest
class TestInputAssignment:
    def test_serialize(self):
        input_assignment = InputAssignment("value", InputValueType.LITERAL)

        # Test if the serialization is correct
        assert input_assignment.serialize() == "value"

        input_assignment.value_type = InputValueType.FLOW_INPUT
        assert input_assignment.serialize() == "${flow.value}"

        input_assignment.value_type = InputValueType.NODE_REFERENCE
        input_assignment.section = "section"
        assert input_assignment.serialize() == "${value.section}"

        input_assignment.property = "property"
        assert input_assignment.serialize() == "${value.section.property}"

        input_assignment.value = AzureContentSafetyConnection
        input_assignment.value_type = InputValueType.LITERAL
        assert input_assignment.serialize() == ConnectionType.serialize_conn(input_assignment.value)

    @pytest.mark.parametrize(
        "serialized_value, expected_value",
        [
            (
                "${value.section.property}",
                InputAssignment("value", InputValueType.NODE_REFERENCE, "section", "property"),
            ),
            (
                "${flow.section.property}",
                FlowInputAssignment("section.property", prefix="flow.", value_type=InputValueType.FLOW_INPUT),
            ),
            ("${value}", InputAssignment("value", InputValueType.NODE_REFERENCE, "output")),
            ("$value", InputAssignment("$value", InputValueType.LITERAL)),
            ("value", InputAssignment("value", InputValueType.LITERAL)),
        ],
    )
    def test_deserialize(self, serialized_value, expected_value):
        input_assignment = InputAssignment.deserialize(serialized_value)
        assert input_assignment == expected_value


@pytest.mark.unittest
class TestFlowInputAssignment:
    @pytest.mark.parametrize(
        "input_value, expected_value",
        [
            ("flow.section.property", True),
            ("inputs.section.property", True),
            ("section.property", False),
            ("", False),
        ],
    )
    def test_is_flow_input(self, input_value, expected_value):
        assert FlowInputAssignment.is_flow_input(input_value) == expected_value

    def test_deserialize(self):
        expected_input = FlowInputAssignment("section.property", prefix="inputs.", value_type=InputValueType.FLOW_INPUT)
        input_assignment = FlowInputAssignment.deserialize("inputs.section.property")
        assert input_assignment == expected_input

        expected_flow = FlowInputAssignment("section.property", prefix="flow.", value_type=InputValueType.FLOW_INPUT)
        flow_assignment = FlowInputAssignment.deserialize("flow.section.property")
        assert flow_assignment == expected_flow

        with pytest.raises(ValueError):
            FlowInputAssignment.deserialize("value")


@pytest.mark.unittest
class TestNode:
    def test_serialize(self):
        node = Node(name="test_node", tool="test_tool", inputs={})
        serialized_node = node.serialize()
        assert serialized_node["name"] == "test_node"
        assert serialized_node["tool"] == "test_tool"
        assert serialized_node["inputs"] == {}

        node = Node(name="test_node", tool="test_tool", inputs={}, aggregation=True)
        serialized_node = node.serialize()
        assert serialized_node["aggregation"]
        assert serialized_node["reduce"]

    def test_deserialize(self):
        data = {"name": "test_node", "tool": "test_tool", "inputs": {}}
        node = Node.deserialize(data)
        assert node.name == "test_node"
        assert node.tool == "test_tool"
        assert node.inputs == {}


@pytest.mark.unittest
class TestFlowInputDefinition:
    def test_serialize(self):
        flow_input = FlowInputDefinition(
            type=ValueType.STRING,
            default="default",
            description="description",
            enum=["enum1", "enum2"],
            is_chat_input=True,
            is_chat_history=True,
        )

        serialized_flow_input = flow_input.serialize()
        assert serialized_flow_input["type"] == ValueType.STRING.value
        assert serialized_flow_input["default"] == "default"
        assert serialized_flow_input["description"] == "description"
        assert serialized_flow_input["enum"] == ["enum1", "enum2"]
        assert serialized_flow_input["is_chat_input"]
        assert serialized_flow_input["is_chat_history"]

        flow_input_reduced = FlowInputDefinition(type=ValueType.BOOL)
        serialized_flow_reduced = flow_input_reduced.serialize()
        assert serialized_flow_reduced["type"] == ValueType.BOOL.value
        assert serialized_flow_reduced.get("default") is None
        assert serialized_flow_reduced.get("is_chat_input") is None
        assert serialized_flow_reduced.get("is_chat_history") is None

    def test_deserialize(self):
        data = {
            "type": ValueType.STRING,
            "default": "default",
            "description": "description",
            "enum": ["enum1", "enum2"],
            "is_chat_input": True,
            "is_chat_history": True,
        }
        flow_input_def = FlowInputDefinition.deserialize(data)
        assert flow_input_def.type == ValueType.STRING.value
        assert flow_input_def.default == "default"
        assert flow_input_def.description == "description"
        assert flow_input_def.enum == ["enum1", "enum2"]
        assert flow_input_def.is_chat_input
        assert flow_input_def.is_chat_history

        data = {
            "type": ValueType.STRING,
        }
        flow_input_def = FlowInputDefinition.deserialize(data)
        assert flow_input_def.type == ValueType.STRING.value
        assert flow_input_def.default is None
        assert flow_input_def.description == ""
        assert flow_input_def.enum == []
        assert flow_input_def.is_chat_input is False
        assert flow_input_def.is_chat_history is None


@pytest.mark.unittest
class TestFlowOutputDefinition:
    def test_serialize(self):
        input_assignment = InputAssignment("value", InputValueType.NODE_REFERENCE)
        flow_output = FlowOutputDefinition(
            type=ValueType.STRING,
            reference=input_assignment,
            description="description",
            evaluation_only=True,
            is_chat_output=True,
        )
        serialized_flow_output = flow_output.serialize()
        assert serialized_flow_output["type"] == ValueType.STRING.value
        assert serialized_flow_output["reference"] == "${value.}"
        assert serialized_flow_output["description"] == "description"
        assert serialized_flow_output["evaluation_only"]
        assert serialized_flow_output["is_chat_output"]

        flow_output_reduced = FlowOutputDefinition(type=ValueType.BOOL, reference=input_assignment)
        serialized_flow_reduced = flow_output_reduced.serialize()
        assert serialized_flow_reduced.get("type") == ValueType.BOOL.value
        assert serialized_flow_reduced.get("reference") == "${value.}"
        assert serialized_flow_reduced.get("description") is None
        assert serialized_flow_reduced.get("evaluation_only") is None
        assert serialized_flow_reduced.get("is_chat_output") is None

    def test_deserialize(self):
        data = {
            "type": ValueType.STRING,
            "reference": "${value.}",
            "description": "description",
            "evaluation_only": True,
            "is_chat_output": True,
        }
        flow_output_def = FlowOutputDefinition.deserialize(data)
        assert flow_output_def.type == ValueType.STRING.value
        assert flow_output_def.reference.value_type == InputValueType.NODE_REFERENCE
        assert flow_output_def.description == "description"
        assert flow_output_def.evaluation_only
        assert flow_output_def.is_chat_output

        data = {"type": ValueType.STRING, "reference": "${flow.section.property}"}
        flow_output_def = FlowOutputDefinition.deserialize(data)
        assert flow_output_def.type == ValueType.STRING.value
        assert flow_output_def.reference.value_type == InputValueType.FLOW_INPUT
        assert flow_output_def.description == ""
        assert flow_output_def.evaluation_only is False
        assert flow_output_def.is_chat_output is False
