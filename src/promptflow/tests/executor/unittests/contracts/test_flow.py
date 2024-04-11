from pathlib import Path

import pytest

from promptflow._sdk.entities._connection import AzureContentSafetyConnection
from promptflow.contracts._errors import FailedToImportModule
from promptflow.contracts.flow import (
    Flow,
    FlowInputAssignment,
    FlowInputDefinition,
    FlowOutputDefinition,
    InputAssignment,
    InputValueType,
    Node,
    NodeVariant,
    NodeVariants,
    ToolSource,
    ToolSourceType,
)
from promptflow.contracts.tool import Tool, ToolType, ValueType

from ...utils import EAGER_FLOWS_ROOT, FLOW_ROOT, get_flow_folder, get_flow_package_tool_definition, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


@pytest.mark.e2etest
class TestFlowContract:
    @pytest.mark.parametrize(
        "flow_folder, expected_connection_names",
        [
            ("web_classification", {"azure_open_ai_connection"}),
            ("basic-with-connection", {"azure_open_ai_connection"}),
            ("flow_with_dict_input_with_variant", {"mock_custom_connection"}),
            ("flow_with_connection_ref_environment_variables", {"azure_open_ai_connection"}),
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
        assert connection_names == ["connection", "connection_2"]
        assert flow.get_connection_input_names_for_node("not_exist") == []

    @pytest.mark.parametrize(
        "file_name, name_from_payload, expected_name",
        [
            ("yaml_with_name.yaml", "name_from_payload", "name_from_payload"),
            ("yaml_with_name.yaml", None, "name_from_yaml"),
            ("yaml_without_name.yaml", "name_from_payload", "name_from_payload"),
            ("yaml_without_name.yaml", None, "flow_name"),
        ],
    )
    def test_flow_name(self, file_name: str, name_from_payload: str, expected_name: str):
        flow_folder = get_flow_folder("flow_name")
        flow = Flow.from_yaml(flow_file=file_name, working_dir=flow_folder, name=name_from_payload)
        assert flow.name == expected_name

    @pytest.mark.parametrize(
        "flow_folder_name, environment_variables_overrides, except_environment_variables",
        [
            pytest.param(
                "flow_with_environment_variables",
                {"env2": "runtime_env2", "env10": "aaaaa"},
                {
                    "env1": "2",
                    "env2": "runtime_env2",
                    "env3": "[1, 2, 3, 4, 5]",
                    "env4": '{"a": 1, "b": "2"}',
                    "env10": "aaaaa",
                },
                id="LoadEnvVariablesWithOverrides",
            ),
            pytest.param(
                "flow_with_environment_variables",
                None,
                {
                    "env1": "2",
                    "env2": "spawn",
                    "env3": "[1, 2, 3, 4, 5]",
                    "env4": '{"a": 1, "b": "2"}',
                },
                id="LoadEnvVariablesWithoutOverrides",
            ),
            pytest.param(
                "simple_hello_world",
                {"env2": "runtime_env2", "env10": "aaaaa"},
                {"env2": "runtime_env2", "env10": "aaaaa"},
                id="LoadEnvVariablesWithoutYamlLevelEnvVariables",
            ),
        ],
    )
    def test_flow_get_environment_variables_with_overrides(
        self, flow_folder_name, environment_variables_overrides, except_environment_variables
    ):
        flow_folder = get_flow_folder(flow_folder_name)
        flow_file = "flow.dag.yaml"
        flow = Flow.from_yaml(flow_file=flow_file, working_dir=flow_folder)
        merged_environment_variables = flow.get_environment_variables_with_overrides(
            environment_variables_overrides=environment_variables_overrides,
        )
        assert merged_environment_variables == except_environment_variables

    @pytest.mark.parametrize(
        "flow_folder_name, folder_root, flow_file, environment_variables_overrides, except_environment_variables",
        [
            pytest.param(
                "flow_with_environment_variables",
                FLOW_ROOT,
                "flow.dag.yaml",
                {"env2": "runtime_env2", "env10": "aaaaa"},
                {
                    "env1": "2",
                    "env2": "runtime_env2",
                    "env3": "[1, 2, 3, 4, 5]",
                    "env4": '{"a": 1, "b": "2"}',
                    "env10": "aaaaa",
                },
                id="LoadEnvVariablesWithOverrides",
            ),
            pytest.param(
                "flow_with_environment_variables",
                FLOW_ROOT,
                "flow.dag.yaml",
                None,
                {
                    "env1": "2",
                    "env2": "spawn",
                    "env3": "[1, 2, 3, 4, 5]",
                    "env4": '{"a": 1, "b": "2"}',
                },
                id="LoadEnvVariablesWithoutOverrides",
            ),
            pytest.param(
                "simple_hello_world",
                FLOW_ROOT,
                "flow.dag.yaml",
                {"env2": "runtime_env2", "env10": "aaaaa"},
                {"env2": "runtime_env2", "env10": "aaaaa"},
                id="LoadEnvVariablesWithoutYamlLevelEnvVariables",
            ),
            pytest.param(
                "simple_with_yaml",
                EAGER_FLOWS_ROOT,
                "entry.py",
                None,
                {},
                id="LoadEnvVariablesForEagerFlow",
            ),
            pytest.param(
                "simple_with_yaml",
                EAGER_FLOWS_ROOT,
                "entry.py",
                {"env2": "runtime_env2", "env10": "aaaaa"},
                {"env2": "runtime_env2", "env10": "aaaaa"},
                id="LoadEnvVariablesForEagerFlowWithOverrides",
            ),
        ],
    )
    def test_load_env_variables(
        self, flow_folder_name, folder_root, flow_file, environment_variables_overrides, except_environment_variables
    ):
        flow_folder = get_flow_folder(flow_folder_name, folder_root)
        merged_environment_variables = Flow.load_env_variables(
            flow_file=flow_file,
            working_dir=flow_folder,
            environment_variables_overrides=environment_variables_overrides,
        )
        assert merged_environment_variables == except_environment_variables


@pytest.mark.unittest
class TestFlow:
    @pytest.mark.parametrize(
        "flow, expected_value",
        [
            (
                Flow(id="flow_id", name="flow_name", nodes=[], inputs={}, outputs={}, tools=[]),
                {
                    "id": "flow_id",
                    "name": "flow_name",
                    "nodes": [],
                    "inputs": {},
                    "outputs": {},
                    "tools": [],
                    "language": "python",
                    "message_format": "basic",
                },
            ),
            (
                Flow(
                    id="flow_id",
                    name="flow_name",
                    nodes=[Node(name="node1", tool="tool1", inputs={})],
                    inputs={"input1": FlowInputDefinition(type=ValueType.STRING)},
                    outputs={"output1": FlowOutputDefinition(type=ValueType.STRING, reference=None)},
                    tools=[],
                ),
                {
                    "id": "flow_id",
                    "name": "flow_name",
                    "nodes": [{"name": "node1", "tool": "tool1", "inputs": {}}],
                    "inputs": {"input1": {"type": ValueType.STRING.value}},
                    "outputs": {"output1": {"type": ValueType.STRING.value}},
                    "tools": [],
                    "language": "python",
                    "message_format": "basic",
                },
            ),
        ],
    )
    def test_flow_serialize(self, flow, expected_value):
        assert flow.serialize() == expected_value

    @pytest.mark.parametrize(
        "data, expected_value",
        [
            (
                {
                    "id": "flow_id",
                    "name": "flow_name",
                    "nodes": [{"name": "node1", "tool": "tool1", "inputs": {}, "outputs": {}}],
                    "inputs": {"input1": {"type": ValueType.STRING.value}},
                    "outputs": {"output1": {"type": ValueType.STRING.value}},
                    "tools": [],
                },
                Flow(
                    id="flow_id",
                    name="flow_name",
                    nodes=[Node(name="node1", tool="tool1", inputs={})],
                    inputs={
                        "input1": FlowInputDefinition(
                            type=ValueType.STRING, description="", enum=[], is_chat_input=False, is_chat_history=None
                        )
                    },
                    outputs={
                        "output1": FlowOutputDefinition(
                            type=ValueType.STRING,
                            reference=InputAssignment(
                                value="", value_type=InputValueType.LITERAL, section="", property=""
                            ),
                            description="",
                            evaluation_only=False,
                            is_chat_output=False,
                        )
                    },
                    tools=[],
                    node_variants={},
                    program_language="python",
                    environment_variables={},
                ),
            ),
        ],
    )
    def test_flow_deserialize(self, data, expected_value):
        assert Flow.deserialize(data) == expected_value

    def test_import_requisites(self):
        tool1 = Tool(name="tool1", type=ToolType.PYTHON, inputs={}, module="yaml")
        tool2 = Tool(name="tool2", type=ToolType.PYTHON, inputs={}, module="module")
        node1 = Node(name="node1", tool="tool1", inputs={}, module="yaml")
        node2 = Node(name="node2", tool="tool2", inputs={}, module="module")

        with pytest.raises(FailedToImportModule) as e:
            Flow._import_requisites([tool1], [node2])
        assert str(e.value).startswith(
            "Failed to import modules with error: Import node 'node2' provider module 'module' failed."
        )

        with pytest.raises(FailedToImportModule) as e:
            Flow._import_requisites([tool2], [node1])
        assert str(e.value).startswith(
            "Failed to import modules with error: Import tool 'tool2' module 'module' failed."
        )

    def test_apply_default_node_variants(self):
        node_variant = NodeVariant(
            node=Node(name="print_val_variant", tool=None, inputs={"input2": None}, use_variants=False),
            description=None,
        )
        node_variants = {
            "print_val": NodeVariants(
                default_variant_id="variant1",
                variants={"variant1": node_variant},
            )
        }
        flow1 = Flow(
            id="test_flow_id",
            name="test_flow",
            nodes=[Node(name="print_val", tool=None, inputs={"input1": None}, use_variants=True)],
            inputs={},
            outputs={},
            tools=[],
            node_variants=node_variants,
        )
        # test when node.use_variants is True
        flow1._apply_default_node_variants()
        assert flow1.nodes[0].use_variants is False
        assert flow1.nodes[0].inputs.keys() == {"input2"}
        assert flow1.nodes[0].name == "print_val"

        flow2 = Flow(
            id="test_flow_id",
            name="test_flow",
            nodes=[Node(name="print_val", tool=None, inputs={"input1": None}, use_variants=False)],
            inputs={},
            outputs={},
            tools=[],
            node_variants=node_variants,
        )
        # test when node.use_variants is False
        tmp_nodes = flow2.nodes
        flow2._apply_default_node_variants()
        assert flow2.nodes == tmp_nodes

    @pytest.mark.parametrize(
        "node_variants",
        [
            (None),
            (
                {
                    "test": NodeVariants(
                        default_variant_id="variant1",
                        variants={
                            "variant1": NodeVariant(
                                node=Node(name="print_val_variant", tool=None, inputs={"input2": None})
                            )
                        },
                    )
                }
            ),
            (
                {
                    "print_val": NodeVariants(
                        default_variant_id="test",
                        variants={
                            "variant1": NodeVariant(
                                node=Node(name="print_val_variant", tool=None, inputs={"input2": None})
                            )
                        },
                    )
                }
            ),
        ],
    )
    def test_apply_default_node_variant(self, node_variants):
        node = Node(name="print_val", tool=None, inputs={"input1": None}, use_variants=True)
        assert Flow._apply_default_node_variant(node, node_variants) == node

    def test_apply_node_overrides(self):
        llm_node = Node(name="llm_node", tool=None, inputs={}, connection="open_ai_connection")
        test_node = Node(
            name="test_node", tool=None, inputs={"test": InputAssignment("test_value1", InputValueType.LITERAL)}
        )
        flow = Flow(id="test_flow_id", name="test_flow", nodes=[llm_node, test_node], inputs={}, outputs={}, tools=[])
        assert flow == flow._apply_node_overrides(None)
        assert flow == flow._apply_node_overrides({})

        node_overrides = {
            "other_node.connection": "some_connection",
        }
        with pytest.raises(ValueError):
            flow._apply_node_overrides(node_overrides)

        node_overrides = {
            "llm_node.connection": "custom_connection",
            "test_node.test": "test_value2",
        }
        flow = flow._apply_node_overrides(node_overrides)
        assert flow.nodes[0].connection == "custom_connection"
        assert flow.nodes[1].inputs["test"].value == "test_value2"

    def test_has_aggregation_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(name="aggre_node", tool=None, inputs={}, aggregation=True)
        flow1 = Flow(id="id", name="name", nodes=[llm_node], inputs={}, outputs={}, tools=[])
        assert not flow1.has_aggregation_node()
        flow2 = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert flow2.has_aggregation_node()

    def test_get_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        flow = Flow(id="id", name="name", nodes=[llm_node], inputs={}, outputs={}, tools=[])
        assert flow.get_node("llm_node") is llm_node
        assert flow.get_node("other_node") is None

    def test_get_tool(self):
        tool = Tool(name="tool", type=ToolType.PYTHON, inputs={})
        flow = Flow(id="id", name="name", nodes=[], inputs={}, outputs={}, tools=[tool])
        assert flow.get_tool("tool") is tool
        assert flow.get_tool("other_tool") is None

    def test_is_reduce_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(name="aggre_node", tool=None, inputs={}, aggregation=True)
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert not flow.is_reduce_node("llm_node")
        assert flow.is_reduce_node("aggre_node")

    def test_is_normal_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(name="aggre_node", tool=None, inputs={}, aggregation=True)
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert flow.is_normal_node("llm_node")
        assert not flow.is_normal_node("aggre_node")

    def test_is_llm_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={}, type=ToolType.LLM)
        aggre_node = Node(name="aggre_node", tool=None, inputs={}, aggregation=True)
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert flow.is_llm_node(llm_node)
        assert not flow.is_llm_node(aggre_node)

    def test_is_referenced_by_flow_output(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(name="aggre_node", tool=None, inputs={}, aggregation=True)
        output = {
            "output": FlowOutputDefinition(
                type=ValueType.STRING, reference=InputAssignment("llm_node", InputValueType.NODE_REFERENCE, "output")
            )
        }
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs=output, tools=[])
        assert flow.is_referenced_by_flow_output(llm_node)
        assert not flow.is_referenced_by_flow_output(aggre_node)

    def test_is_node_referenced_by(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(
            name="aggre_node",
            tool=None,
            inputs={"input": InputAssignment(value="llm_node", value_type=InputValueType.NODE_REFERENCE)},
            aggregation=True,
        )
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert not flow.is_node_referenced_by(aggre_node, llm_node)
        assert flow.is_node_referenced_by(llm_node, aggre_node)

    def test_is_referenced_by_other_node(self):
        llm_node = Node(name="llm_node", tool=None, inputs={})
        aggre_node = Node(
            name="aggre_node",
            tool=None,
            inputs={"input": InputAssignment(value="llm_node", value_type=InputValueType.NODE_REFERENCE)},
            aggregation=True,
        )
        flow = Flow(id="id", name="name", nodes=[llm_node, aggre_node], inputs={}, outputs={}, tools=[])
        assert not flow.is_referenced_by_other_node(aggre_node)
        assert flow.is_referenced_by_other_node(llm_node)

    def test_is_chat_flow(self):
        chat_input = {"question": FlowInputDefinition(type=ValueType.STRING, is_chat_input=True)}
        standard_flow = Flow(id="id", name="name", nodes=[], inputs={}, outputs={}, tools=[])
        chat_flow = Flow(id="id", name="name", nodes=[], inputs=chat_input, outputs={}, tools=[])
        assert not standard_flow.is_chat_flow()
        assert chat_flow.is_chat_flow()

    def test_get_chat_input_name(self):
        chat_input = {"question": FlowInputDefinition(type=ValueType.STRING, is_chat_input=True)}
        standard_flow = Flow(id="id", name="name", nodes=[], inputs={}, outputs={}, tools=[])
        chat_flow = Flow(id="id", name="name", nodes=[], inputs=chat_input, outputs={}, tools=[])
        assert standard_flow.get_chat_input_name() is None
        assert chat_flow.get_chat_input_name() == "question"

    def test_get_chat_output_name(self):
        chat_output = {"answer": FlowOutputDefinition(type=ValueType.STRING, reference=None, is_chat_output=True)}
        standard_flow = Flow(id="id", name="name", nodes=[], inputs={}, outputs={}, tools=[])
        chat_flow = Flow(id="id", name="name", nodes=[], inputs={}, outputs=chat_output, tools=[])
        assert standard_flow.get_chat_output_name() is None
        assert chat_flow.get_chat_output_name() == "answer"

    def test_replace_with_variant(self):
        node0 = Node(name="node0", tool=None, inputs={"input0": None}, use_variants=True)
        node1 = Node(name="node1", tool="tool1", inputs={"input1": None}, use_variants=False)
        node2 = Node(name="node2", tool="tool2", inputs={"input2": None}, use_variants=False)
        node_variant = Node(name="node0", tool="tool3", inputs={"input3": None}, use_variants=False)
        node_variants = {
            "print_val": NodeVariants(
                default_variant_id="variant1",
                variants={"variant1": NodeVariant(node_variant, None)},
            )
        }
        flow = Flow(
            id="test_flow_id",
            name="test_flow",
            nodes=[node0, node1, node2],
            inputs={},
            outputs={},
            tools=[],
            node_variants=node_variants,
        )
        # flow = Flow.from_yaml(get_yaml_file("web_classification"))
        tool_cnt = len(flow.tools)
        flow._replace_with_variant(node_variant, [flow.nodes[1].tool, flow.nodes[2].tool])
        assert "input3" in flow.nodes[0].inputs
        assert flow.nodes[0].tool == "tool3"
        assert len(flow.tools) == tool_cnt + 2


@pytest.mark.unittest
class TestInputAssignment:
    @pytest.mark.parametrize(
        "value, expected_value",
        [
            (InputAssignment("value", InputValueType.LITERAL), "value"),
            (InputAssignment("value", InputValueType.FLOW_INPUT), "${flow.value}"),
            (InputAssignment("value", InputValueType.NODE_REFERENCE, "section"), "${value.section}"),
            (
                InputAssignment("value", InputValueType.NODE_REFERENCE, "section", "property"),
                "${value.section.property}",
            ),
            (InputAssignment(AzureContentSafetyConnection, InputValueType.LITERAL, "section", "property"), "ABCMeta"),
        ],
    )
    def test_serialize(self, value, expected_value):
        assert value.serialize() == expected_value

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

    @pytest.mark.parametrize(
        "serialized_reference, expected_value",
        [
            ("input", InputAssignment("input", InputValueType.NODE_REFERENCE, "output")),
            ("flow.section", FlowInputAssignment("section", value_type=InputValueType.FLOW_INPUT, prefix="flow.")),
            (
                "flow.section.property",
                FlowInputAssignment("section.property", value_type=InputValueType.FLOW_INPUT, prefix="flow."),
            ),
        ],
    )
    def test_deserialize_reference(self, serialized_reference, expected_value):
        assert InputAssignment.deserialize_reference(serialized_reference) == expected_value

    @pytest.mark.parametrize(
        "serialized_node_reference, expected_value",
        [
            ("value", InputAssignment("value", InputValueType.NODE_REFERENCE, "output")),
            ("value.section", InputAssignment("value", InputValueType.NODE_REFERENCE, "section")),
            ("value.section.property", InputAssignment("value", InputValueType.NODE_REFERENCE, "section", "property")),
        ],
    )
    def test_deserialize_node_reference(self, serialized_node_reference, expected_value):
        assert InputAssignment.deserialize_node_reference(serialized_node_reference) == expected_value


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
        assert FlowInputAssignment.deserialize("inputs.section.property") == expected_input

        expected_flow = FlowInputAssignment("section.property", prefix="flow.", value_type=InputValueType.FLOW_INPUT)
        assert FlowInputAssignment.deserialize("flow.section.property") == expected_flow

        with pytest.raises(ValueError):
            FlowInputAssignment.deserialize("value")


@pytest.mark.unittest
class TestToolSource:
    @pytest.mark.parametrize(
        "tool_source, expected_value",
        [
            ({}, ToolSource(type=ToolSourceType.Code)),
            ({"type": ToolSourceType.Code.value}, ToolSource(type=ToolSourceType.Code)),
            (
                {"type": ToolSourceType.Package.value, "tool": "tool", "path": "path"},
                ToolSource(type=ToolSourceType.Package, tool="tool", path="path"),
            ),
        ],
    )
    def test_deserialize(self, tool_source, expected_value):
        assert ToolSource.deserialize(tool_source) == expected_value


@pytest.mark.unittest
class TestNode:
    @pytest.mark.parametrize(
        "node, expected_value",
        [
            (
                Node(name="test_node", tool="test_tool", inputs={}),
                {"name": "test_node", "tool": "test_tool", "inputs": {}},
            ),
            (
                Node(name="test_node", tool="test_tool", inputs={}, aggregation=True),
                {"name": "test_node", "tool": "test_tool", "inputs": {}, "aggregation": True, "reduce": True},
            ),
        ],
    )
    def test_serialize(self, node, expected_value):
        assert node.serialize() == expected_value

    @pytest.mark.parametrize(
        "data, expected_value",
        [
            (
                {"name": "test_node", "tool": "test_tool", "inputs": {}},
                Node(name="test_node", tool="test_tool", inputs={}),
            ),
            (
                {"name": "test_node", "tool": "test_tool", "inputs": {}, "aggregation": True},
                Node(name="test_node", tool="test_tool", inputs={}, aggregation=True),
            ),
        ],
    )
    def test_deserialize(self, data, expected_value):
        assert Node.deserialize(data) == expected_value


@pytest.mark.unittest
class TestFlowInputDefinition:
    @pytest.mark.parametrize(
        "value, expected_value",
        [
            (FlowInputDefinition(type=ValueType.BOOL), {"type": ValueType.BOOL.value}),
            (
                FlowInputDefinition(
                    type=ValueType.STRING,
                    default="default",
                    description="description",
                    enum=["enum1", "enum2"],
                    is_chat_input=True,
                    is_chat_history=True,
                ),
                {
                    "type": ValueType.STRING.value,
                    "default": "default",
                    "description": "description",
                    "enum": ["enum1", "enum2"],
                    "is_chat_input": True,
                    "is_chat_history": True,
                },
            ),
        ],
    )
    def test_serialize(self, value, expected_value):
        assert value.serialize() == expected_value

    @pytest.mark.parametrize(
        "data, expected_value",
        [
            (
                {
                    "type": ValueType.STRING,
                    "default": "default",
                    "description": "description",
                    "enum": ["enum1", "enum2"],
                    "is_chat_input": True,
                    "is_chat_history": True,
                },
                FlowInputDefinition(
                    type=ValueType.STRING,
                    default="default",
                    description="description",
                    enum=["enum1", "enum2"],
                    is_chat_input=True,
                    is_chat_history=True,
                ),
            ),
            (
                {
                    "type": ValueType.STRING,
                },
                FlowInputDefinition(
                    type=ValueType.STRING, description="", enum=[], is_chat_input=False, is_chat_history=None
                ),
            ),
        ],
    )
    def test_deserialize(self, data, expected_value):
        assert FlowInputDefinition.deserialize(data) == expected_value


@pytest.mark.unittest
class TestFlowOutputDefinition:
    @pytest.mark.parametrize(
        "value, expected_value",
        [
            (FlowOutputDefinition(type=ValueType.BOOL, reference=None), {"type": ValueType.BOOL.value}),
            (
                FlowOutputDefinition(
                    type=ValueType.STRING,
                    reference=InputAssignment("value", InputValueType.NODE_REFERENCE),
                    description="description",
                    evaluation_only=True,
                    is_chat_output=True,
                ),
                {
                    "type": ValueType.STRING.value,
                    "reference": "${value.}",
                    "description": "description",
                    "evaluation_only": True,
                    "is_chat_output": True,
                },
            ),
        ],
    )
    def test_serialize(self, value, expected_value):
        assert value.serialize() == expected_value

    @pytest.mark.parametrize(
        "data, expected_value",
        [
            (
                {
                    "type": ValueType.STRING,
                },
                FlowOutputDefinition(
                    type=ValueType.STRING,
                    reference=InputAssignment("", InputValueType.LITERAL),
                ),
            ),
        ],
    )
    def test_deserialize(self, data, expected_value):
        assert FlowOutputDefinition.deserialize(data) == expected_value
