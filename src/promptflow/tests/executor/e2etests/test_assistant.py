import os

import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_flow_folder, get_yaml_file


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
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
        name = line_input["name"]
        assert f"Thanks for your help, {name}!" == flow_result.output["answer"]["content"][0]["text"]["value"]
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
