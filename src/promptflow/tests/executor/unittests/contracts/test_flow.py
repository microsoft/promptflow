import pytest
import yaml
from pathlib import Path

from promptflow.contracts._errors import NodeConditionConflict
from promptflow.contracts.flow import Flow, InputValueType, InputAssignment, FlowInputAssignment, Node, \
    FlowInputDefinition, FlowOutputDefinition
from promptflow.contracts.tool import ConnectionType, Tool, ToolType, ValueType
from promptflow._sdk.entities._connection import AzureContentSafetyConnection
from ...utils import WRONG_FLOW_ROOT, get_flow_package_tool_definition, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


# Is this unittest or e2etest?
@pytest.mark.e2etest
class TestFlowContract:
    @pytest.mark.parametrize(
        "flow_folder, expected_connection_names",
        [
            ("web_classification", {"azure_open_ai_connection"}),
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
        assert connection_names == {'azure_open_ai_connection'}

    def test_flow_get_connection_input_names_for_node(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        flow_file = flow_folder / "flow.dag.yaml"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tool_definition)
        flow = Flow.from_yaml(flow_file)
        connection_names = flow.get_connection_input_names_for_node(flow.nodes[0].name)
        assert connection_names == ['connection']

    def test_node_condition_conflict(self):
        flow_folder = "node_condition_conflict"
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with pytest.raises(NodeConditionConflict) as e:
            with open(flow_yaml, "r") as fin:
                Flow.deserialize(yaml.safe_load(fin))
        error_message = "Node 'test_node' can't have both skip and activate condition."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))


@pytest.mark.unittest
class TestInputAssignment:
    def test_serialize(self):
        input_assignment = InputAssignment('value', InputValueType.LITERAL)
        
        # Test if the serialization is correct
        assert input_assignment.serialize() == 'value'

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
            ("${value.section.property}", InputAssignment("value", InputValueType.NODE_REFERENCE, "section", "property")),
            ("${flow.section.property}", FlowInputAssignment("section.property", prefix="flow.", value_type=InputValueType.FLOW_INPUT)),
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
        assert serialized_node['name'] == "test_node"
        assert serialized_node['tool'] == "test_tool"
        assert serialized_node['inputs'] == {}

        node = Node(name="test_node", tool="test_tool", inputs={}, aggregation=True)
        serialized_node = node.serialize()
        assert serialized_node['aggregation']
        assert serialized_node['reduce']


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
            is_chat_history=True)
        
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
            "is_chat_history": True
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
        input_assignment = InputAssignment('value', InputValueType.NODE_REFERENCE)
        flow_output = FlowOutputDefinition(
            type=ValueType.STRING,
            reference=input_assignment,
            description="description",
            evaluation_only=True,
            is_chat_output=True
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
            "is_chat_output": True
        }
        flow_output_def = FlowOutputDefinition.deserialize(data)
        assert flow_output_def.type == ValueType.STRING.value
        assert flow_output_def.reference.value_type == InputValueType.NODE_REFERENCE
        assert flow_output_def.description == "description"
        assert flow_output_def.evaluation_only
        assert flow_output_def.is_chat_output

        data = {
            "type": ValueType.STRING,
            "reference": "${flow.section.property}"
        }
        flow_output_def = FlowOutputDefinition.deserialize(data)
        assert flow_output_def.type == ValueType.STRING.value
        assert flow_output_def.reference.value_type == InputValueType.FLOW_INPUT
        assert flow_output_def.description == ""
        assert flow_output_def.evaluation_only is False
        assert flow_output_def.is_chat_output is False
