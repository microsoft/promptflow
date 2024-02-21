import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_yaml_file


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestLangchain:
    @pytest.mark.parametrize(
        "flow_folder, line_input",
        [
            ("assistant-tool-with-connection", {"name": "Mike"}),
        ],
    )
    def test_flow_with_connection(self, flow_folder, line_input, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        flow_result = executor.exec_line(line_input)
        print(flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert len(flow_result.output["answer"]["content"]) == 1
        assert flow_result.output["answer"]["content"][0]["type"] == "text"
        expected_text = f"Thanks for your help, {line_input['name']}!"
        assert flow_result.output["answer"]["content"][0]["text"]["value"] == expected_text
        assert flow_result.output["thread_id"]
