import json
import os

import pytest

from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import get_flow_folder, get_yaml_file

FLOW_WITH_NO_FILE = "chat-with-assistant-no-file"
FLOW_WITH_FILE = "assistant-with-file"


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestAssistant:
    @pytest.mark.parametrize(
        "flow_folder",
        [
            FLOW_WITH_NO_FILE,
        ],
    )
    def test_flow_run_wo_file_in_assistant(self, flow_folder, dev_connections):
        os.chdir(get_flow_folder(flow_folder))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        line_input = {
            "chat_history": [],
            "question": "I am going to swim today for 30 min in Guangzhou city, how much calories will I burn?",
        }
        flow_result = executor.exec_line(line_input)
        # verify there is no file related attributes(file_id_references etc) and only with text
        assert flow_result.output["answer"]
        assert flow_result.output["answer"]["file_id_references"] == {}
        assert flow_result.output["answer"]["content"]
        assert flow_result.output["answer"]["content"][0]["type"] == "text"
        assert flow_result.output["answer"]["content"][0]["text"]["annotations"] == []
        # verify thread are created and in output result
        assert flow_result.output["thread_id"] == flow_result.node_run_infos["get_or_create_thread"].output
        # verify traces covers the two nodes
        assert len(flow_result.run_info.api_calls[0]["children"]) == 2
        # verify tools are invoked
        assert "get_temperature" in json.dumps(flow_result.run_info.api_calls[0]["children"][1])
        assert "get_calorie_by_swimming" in json.dumps(flow_result.run_info.api_calls[0]["children"][1])
        assert flow_result.run_info.status == Status.Completed

    @pytest.mark.parametrize(
        "flow_folder",
        [
            FLOW_WITH_FILE,
        ],
    )
    def test_flow_run_with_file_in_assistant(self, flow_folder, dev_connections):
        os.chdir(get_flow_folder(flow_folder))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        line_input = {
            "assistant_input": [
                "The provided file contains end-of-day (EOD) stock prices for companies A and B across various dates "
                "in March. However, it does not include the EOD stock prices for Company C.",
                {"type": "file_path", "file_path": {"path": "./stock_price.csv"}},
                {
                    "type": "text",
                    "text": "Please draw a line chart with the stock price of the company A, B and C "
                    "and return a CVS file with the data.",
                },
            ],
        }
        flow_result = executor.exec_line(line_input)
        # verify file_id_reference are created and in output result
        file_id_reference = flow_result.output["assistant_output"]["file_id_references"]
        assert file_id_reference
        # verify file_id_reference and content are matched
        for output in flow_result.output["assistant_output"]["content"]:
            if output["type"] == "image_file":
                image_file_id = output["image_file"]["file_id"]
                assert isinstance(file_id_reference[image_file_id]["content"], Image)
                assert image_file_id in file_id_reference[image_file_id]["url"]
            if output["type"] == "text":
                assert output["text"]["value"]
                file_id = output["text"]["annotations"][0]["file_path"]["file_id"]
                assert file_id in file_id_reference[file_id]["url"]
        # verify thread are created and in output result
        assert flow_result.output["thread_id"] == flow_result.node_run_infos["get_or_create_thread"].output
        # verify traces covers the two nodes
        assert len(flow_result.run_info.api_calls[0]["children"]) == 2
        # verify tools are invoked
        assert "get_stock_eod_price" in json.dumps(flow_result.run_info.api_calls[0]["children"][1])
        assert flow_result.run_info.status == Status.Completed
