from pathlib import Path

import pytest
import yaml

from promptflow.contracts._errors import NodeConditionConflict
from promptflow.contracts.flow import Flow

from ...utils import WRONG_FLOW_ROOT, get_yaml_file

TEST_CONFIG = Path(__file__).parent.parent.parent.parent / "test_configs"
VARIANT_LLM_FLOW_PATH = TEST_CONFIG / "flows" / "web_classification"
VARIANT_PYTHON_FLOW_PATH = TEST_CONFIG / "flows" / "flow_with_dict_input_with_variant"


@pytest.mark.unittest
class TestFlowContract:
    def test_flow_get_connection_names(self):
        flow = Flow.from_yaml(VARIANT_LLM_FLOW_PATH / "flow.dag.yaml")
        assert flow.get_connection_names() == {"azure_open_ai_connection"}
        flow = Flow.from_yaml(VARIANT_PYTHON_FLOW_PATH / "flow.dag.yaml")
        assert flow.get_connection_names() == {"mock_custom_connection"}

    def test_get_connection_input_names_for_node(self):
        # Connection input exists only in python node
        variant_python_node_flow_path = TEST_CONFIG / "flows" / "flow_with_dict_input_with_variant"
        flow = Flow.from_yaml(variant_python_node_flow_path / "flow.dag.yaml")
        assert flow.get_connection_input_names_for_node("print_val") == ["conn"]

    def test_node_condition_conflict(self):
        flow_folder = "node_condition_conflict"
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with pytest.raises(NodeConditionConflict) as e:
            with open(flow_yaml, "r") as fin:
                Flow.deserialize(yaml.safe_load(fin))
        error_message = "Node 'test_node' can't have both skip and activate condition."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))
