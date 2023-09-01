from pathlib import Path

import pytest

from promptflow.contracts.flow import Flow

from ...utils import get_flow_package_tool_definition

TEST_CONFIG = Path(__file__).parent.parent.parent.parent / "test_configs"
VARIANT_LLM_FLOW_PATH = TEST_CONFIG / "flows" / "web_classification"
VARIANT_PYTHON_FLOW_PATH = TEST_CONFIG / "flows" / "flow_with_dict_input_with_variant"
PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


@pytest.mark.unittest
class TestFlowContracts:
    def test_flow_get_connection_names_with_variants(self):
        flow = Flow.from_yaml(VARIANT_LLM_FLOW_PATH / "flow.dag.yaml")
        assert flow.get_connection_names() == {"azure_open_ai_connection"}
        flow = Flow.from_yaml(VARIANT_PYTHON_FLOW_PATH / "flow.dag.yaml")
        assert flow.get_connection_names() == {"mock_custom_connection"}

    def test_flow_get_connection_input_names_for_node_with_variants(self):
        # Connection input exists only in python node
        variant_python_node_flow_path = TEST_CONFIG / "flows" / "flow_with_dict_input_with_variant"
        flow = Flow.from_yaml(variant_python_node_flow_path / "flow.dag.yaml")
        assert flow.get_connection_input_names_for_node("print_val") == ["conn"]

    def test_flow_get_connection_names(self, mocker):
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
