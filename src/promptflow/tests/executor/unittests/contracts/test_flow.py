from pathlib import Path

import pytest

from promptflow.contracts.flow import Flow

from ...utils import get_flow_package_tool_definition

PACKAGE_TOOL_BASE = Path(__file__).parent.parent.parent / "package_tools"


@pytest.mark.unittest
class TestFlow:
    def test_get_connection_names(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        flow_file = flow_folder / "flow.dag.yaml"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tool_definition)
        flow = Flow.from_yaml(flow_file)
        connection_names = flow.get_connection_names()
        assert connection_names == {'azure_open_ai_connection'}

    def test_get_connection_input_names_for_node(self, mocker):
        flow_folder = PACKAGE_TOOL_BASE / "custom_llm_tool"
        flow_file = flow_folder / "flow.dag.yaml"
        package_tool_definition = get_flow_package_tool_definition(flow_folder)
        mocker.patch("promptflow._core.tools_manager.collect_package_tools", return_value=package_tool_definition)
        flow = Flow.from_yaml(flow_file)
        connection_names = flow.get_connection_input_names_for_node(flow.nodes[0].name)
        assert connection_names == ['connection']
