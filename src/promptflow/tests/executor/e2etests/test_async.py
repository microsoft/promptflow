import os
import shutil
from pathlib import Path

import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor.flow_executor import execute_flow_async
from promptflow.storage._run_storage import DefaultRunStorage

from ..utils import get_flow_folder, get_yaml_file, is_image_file

SAMPLE_FLOW = "web_classification_no_variants"


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
            ("async_tools", {"ouput1": "Hello", "output2": "Hello"}),
            ("async_tools_with_sync_tools", {"ouput1": "Hello", "output2": "Hello"}),
        ],
    )
    async def test_exec_line_async(self, folder_name, expected_result):
        os.chdir(get_flow_folder(folder_name))
        executor = FlowExecutor.create(get_yaml_file(folder_name), {})
        flow_result = await executor.exec_line_async({"input_str": "Hello"})
        assert flow_result.run_info.status == Status.Completed
        assert flow_result.output == expected_result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "output_dir_name, intermediate_dir_name, run_aggregation, expected_node_counts",
        [
            ("output", "intermediate", True, 2),
            ("output_1", "intermediate_1", False, 1),
        ],
    )
    async def test_execute_flow_async(
        self, output_dir_name: str, intermediate_dir_name: str, run_aggregation: bool, expected_node_counts: int
    ):
        flow_folder = get_flow_folder("eval_flow_with_simple_image")
        # prepare output folder
        output_dir = flow_folder / output_dir_name
        intermediate_dir = flow_folder / intermediate_dir_name
        output_dir.mkdir(exist_ok=True)
        intermediate_dir.mkdir(exist_ok=True)

        storage = DefaultRunStorage(base_dir=flow_folder, sub_dir=Path(intermediate_dir_name))
        line_result = await execute_flow_async(
            flow_file=get_yaml_file(flow_folder),
            working_dir=flow_folder,
            output_dir=Path(output_dir_name),
            inputs={},
            connections={},
            run_aggregation=run_aggregation,
            storage=storage,
        )
        assert line_result.run_info.status == Status.Completed
        assert len(line_result.node_run_infos) == expected_node_counts
        assert all(is_image_file(output_file) for output_file in output_dir.iterdir())
        assert all(is_image_file(output_file) for output_file in intermediate_dir.iterdir())
        # clean up output folder
        shutil.rmtree(output_dir)
        shutil.rmtree(intermediate_dir)
