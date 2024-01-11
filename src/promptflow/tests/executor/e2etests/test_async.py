import os

import pytest

from promptflow.executor import FlowExecutor

from ..utils import get_flow_folder, get_yaml_file


@pytest.mark.e2etest
class TestAsync:
    @pytest.mark.parametrize(
        "folder_name, nodes",
        [
            ("async_tools", ["async_passthrough", "async_passthrough1", "async_passthrough2"]),
            ("async_tools_with_sync_tools", ["async_passthrough", "async_passthrough1", "sync_passthrough1"]),
        ],
    )
    def test_executor_node_concurrency(self, folder_name, nodes):
        os.chdir(get_flow_folder(folder_name))
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})

        def get_node_times(api_calls, nodes):
            node_times = {node: {"start": None, "end": None} for node in nodes}
            for api_call in api_calls[0]["children"]:
                if api_call["node_name"] in nodes:
                    node_times[api_call["node_name"]]["start"] = api_call["start_time"]
                    node_times[api_call["node_name"]]["end"] = api_call["end_time"]
            return node_times

        # When node_concurrency is 1, nodes execute one by one
        flow_result = executor.exec_line({"input_str": "Hello"}, node_concurrency=1)
        node_times = get_node_times(flow_result.run_info.api_calls, nodes)
        assert node_times[nodes[0]]["end"] < node_times[nodes[1]]["start"]
        assert node_times[nodes[1]]["end"] < node_times[nodes[2]]["start"]

        # When node_concurrency is 2, two nodes execute concurrently
        flow_result = executor.exec_line({"input_str": "Hello"}, node_concurrency=2)
        node_times = get_node_times(flow_result.run_info.api_calls, nodes)
        assert node_times[nodes[1]]["start"] < node_times[nodes[2]]["end"]
        assert node_times[nodes[2]]["start"] < node_times[nodes[1]]["end"]
