import pytest
import yaml
from pathlib import Path

from promptflow.contracts._errors import NodeConditionConflict
from promptflow.contracts.flow import Flow


from ...utils import WRONG_FLOW_ROOT, get_flow_package_tool_definition, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


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
