import os
import pytest
from promptflow.executor import FlowExecutor
from ..utils import get_flow_folder, get_yaml_file
from promptflow.contracts.run_info import Status


@pytest.mark.asyncio
@pytest.mark.e2etest
class TestAsync:
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
