import pytest
import yaml

from promptflow.contracts._errors import NodeConditionConflict
from promptflow.contracts.flow import Flow

from ...utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.unittest
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

    def test_get_connection_input_names_for_node(self):
        # Connection input exists only in python node
        flow_folder = "flow_with_dict_input_with_variant"
        flow_yaml = get_yaml_file(flow_folder)
        flow = Flow.from_yaml(flow_yaml)
        assert flow.get_connection_input_names_for_node("print_val") == ["conn"]

    def test_node_condition_conflict(self):
        flow_folder = "node_condition_conflict"
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with pytest.raises(NodeConditionConflict) as e:
            with open(flow_yaml, "r") as fin:
                Flow.deserialize(yaml.safe_load(fin))
        error_message = "Node 'test_node' can't have both skip and activate condition."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))
