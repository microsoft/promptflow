from pathlib import Path

import pytest

from promptflow.contracts.flow import Flow

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
