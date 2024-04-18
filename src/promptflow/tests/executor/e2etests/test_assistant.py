import os
import sys
from pathlib import Path

import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_flow_folder, get_flow_package_tool_definition, get_yaml_file

PACKAGE_TOOL_BASE = Path(__file__).parent.parent / "package_tools"
PACKAGE_TOOL_ENTRY = "promptflow._core.tools_manager.collect_package_tools"
sys.path.insert(0, str(PACKAGE_TOOL_BASE.resolve()))


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
@pytest.mark.skip(reason="openai breaking release; fixing on the way")
class TestAssistant:
    @pytest.mark.parametrize(
        "flow_folder, line_input",
        [
            ("assistant-tool-with-connection", {"name": "Mike"}),
        ],
    )
    def test_assistant_tool_with_connection(self, flow_folder, line_input, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(line_input)
        print(flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert len(flow_result.output["answer"]["content"]) == 1
        assert flow_result.output["answer"]["content"][0]["type"] == "text"
        assert flow_result.output["thread_id"]

    @pytest.mark.parametrize(
        "flow_folder, line_input",
        [
            (
                "food-calorie-assistant",
                {
                    "assistant_input": [
                        {"type": "text", "text": "Please generate the calories report for my meal plan."},
                        {"type": "file_path", "file_path": {"path": "./meal_plan.csv"}},
                    ]
                },
            ),
        ],
    )
    def test_assistant_with_image(self, flow_folder, line_input, dev_connections):
        os.chdir(get_flow_folder(flow_folder))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(line_input)
        print(flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert len(flow_result.output["assistant_output"]["content"]) > 0
        assert len(flow_result.output["assistant_output"]["file_id_references"]) > 0
        assert flow_result.output["thread_id"]

    @pytest.mark.parametrize(
        "flow_folder",
        [
            "assistant-with-package-tool",
        ],
    )
    def test_assistant_package_tool_with_conn(self, mocker, flow_folder, dev_connections):
        package_tool_definition = get_flow_package_tool_definition(flow_folder)

        with mocker.patch(PACKAGE_TOOL_ENTRY, return_value=package_tool_definition):
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, raise_ex=True)
            flow_result = executor.exec_line({})
            assert flow_result.run_info.status == Status.Completed
