import os
import pytest
from promptflow.executor import FlowExecutor
from ..utils import get_flow_folder, get_yaml_file


@pytest.mark.e2etest
class TestAsync:
    @pytest.mark.parametrize(
        "folder_name, concurrency_levels",
        [
            ("async_tools", [1, 2, 3]),
            ("async_tools_with_sync_tools", [1, 2, 3]),
        ],
    )
    def test_executor_node_concurrency(self, folder_name, concurrency_levels):
        os.chdir(get_flow_folder(folder_name))
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})
        for concurrency in concurrency_levels:
            flow_result = executor.exec_line({"input_str": "Hello"}, node_concurrency=concurrency)
            max_concurrency = self.calculate_max_concurrency(flow_result)
            assert max_concurrency <= concurrency

    def calculate_max_concurrency(self, flow_result):
        timeline = []
        api_calls = flow_result.run_info.api_calls[0]["children"]
        print("api_calls:", api_calls)
        for api_call in api_calls:
            timeline.append(("start", api_call["start_time"]))
            timeline.append(("end", api_call["end_time"]))
        timeline.sort(key=lambda x: x[1])
        print("timeline", timeline)
        current_concurrency = 0
        max_concurrency = 0

        for event, _ in timeline:
            if event == "start":
                current_concurrency += 1
                max_concurrency = max(max_concurrency, current_concurrency)
            elif event == "end":
                current_concurrency -= 1

        return max_concurrency
