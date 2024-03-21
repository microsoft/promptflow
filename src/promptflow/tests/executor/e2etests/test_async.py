import os
import pytest
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from ..utils import get_flow_folder, get_yaml_file


@pytest.mark.e2etest
class TestAsync:
    @pytest.mark.parametrize(
        "folder_name, concurrency_levels, expected_concurrency",
        [
            ("async_tools", [1, 2, 3], [1, 2, 2]),
            ("async_tools_with_sync_tools", [1, 2, 3], [1, 2, 2]),
        ],
    )
    def test_executor_node_concurrency(self, folder_name, concurrency_levels, expected_concurrency):
        os.chdir(get_flow_folder(folder_name))
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})

        def calculate_max_concurrency(flow_result):
            timeline = []
            api_calls = flow_result.run_info.api_calls[0]["children"]
            for api_call in api_calls:
                timeline.append(("start", api_call["start_time"]))
                timeline.append(("end", api_call["end_time"]))
            timeline.sort(key=lambda x: x[1])
            current_concurrency = 0
            max_concurrency = 0
            for event, _ in timeline:
                if event == "start":
                    current_concurrency += 1
                    max_concurrency = max(max_concurrency, current_concurrency)
                elif event == "end":
                    current_concurrency -= 1
            return max_concurrency

        for i in range(len(concurrency_levels)):
            concurrency = concurrency_levels[i]
            flow_result = executor.exec_line({"input_str": "Hello"}, node_concurrency=concurrency)
            max_concurrency = calculate_max_concurrency(flow_result)
            assert max_concurrency == expected_concurrency[i]
            assert max_concurrency <= concurrency

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "folder_name, expected_result",
        [
            ("async_tools", {'ouput1': 'Hello', 'output2': 'Hello'}),
            ("async_tools_with_sync_tools", {'ouput1': 'Hello', 'output2': 'Hello'}),
        ],
    )
    async def test_exec_line_async(self, folder_name, expected_result):
        os.chdir(get_flow_folder(folder_name))
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})
        flow_result = await executor.exec_line_async({"input_str": "Hello"})
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.output == expected_result
