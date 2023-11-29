from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from promptflow.batch._batch_engine import BatchEngine
from promptflow.contracts.run_info import Status

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file

LINE_RESULT_DICT = {
    "output": {"answer": "Hello world!"},
    "aggregation_inputs": {},
    "run_info": {
        "run_id": "17dc81f88-87ya-7027-37p9-2eb56daab644",
        "status": "Completed",
        "inputs": {
            "question": "What is the promptflow?",
        },
        "output": {"answer": "Hello world!"},
        "parent_run_id": "17dc81f88-87ya-7027-37p9-2eb56daab644",
        "root_run_id": "17dc81f88-87ya-7027-37p9-2eb56daab644",
        "start_time": "2023-11-24T06:03:20.2685529Z",
        "end_time": "2023-11-24T06:03:20.2688869Z",
        "index": {
            "question": "What is the promptflow?",
        },
        "system_metrics": {"duration": "00:00:00.0003340", "total_tokens": 0},
        "result": {"answer": "Hello world!"},
    },
    "node_run_infos": {
        "get_answer": {
            "node": "get_answer",
            "flow_run_id": "17dc81f88-87ya-7027-37p9-2eb56daab644",
            "parent_run_id": "17dc81f88-87ya-7027-37p9-2eb56daab644",
            "run_id": "37081f88-21cf-4653-8004-2ebeb31ab644",
            "status": "Completed",
            "inputs": {
                "question": "What is the promptflow?",
            },
            "output": "Hello world!",
            "start_time": "2023-11-24T06:03:20.2688262Z",
            "end_time": "2023-11-24T06:03:20.268858Z",
            "index": {
                "question": "What is the promptflow?",
            },
            "system_metrics": {"duration": "00:00:00.0000318", "total_tokens": 0},
            "result": "Hello world!",
        }
    },
}


@pytest.mark.unittest
class TestExecutorProxy:
    def test_batch_with_csharp_executor_proxy(self):
        # mock the response of the execution api
        mock_execution = MagicMock()
        mock_execution.status_code = 200
        mock_execution.json.return_value = LINE_RESULT_DICT
        mock_execution_response = AsyncMock(return_value=mock_execution)

        # mock the api endpoint is healthy
        mock_health = MagicMock()
        mock_health.status_code = 200
        mock_health_response = AsyncMock(return_value=mock_health)

        # Patch the original client.post with the mock_post
        with patch("promptflow.batch._base_executor_proxy.httpx.AsyncClient.get", mock_health_response), patch(
            "promptflow.batch._base_executor_proxy.httpx.AsyncClient.post", mock_execution_response
        ):
            flow_folder = "csharp_flow"
            mem_run_storage = MemoryRunStorage()
            batch_engine = BatchEngine(
                get_yaml_file(flow_folder), get_flow_folder(flow_folder), storage=mem_run_storage
            )
            # prepare the inputs
            input_dirs = {"data": get_flow_inputs_file(flow_folder)}
            inputs_mapping = {"question": "${data.question}"}
            output_dir = Path(mkdtemp())
            # submit a batch run
            batch_result = batch_engine.run(input_dirs, inputs_mapping, output_dir)
            assert batch_result.status == Status.Completed
            assert batch_result.completed_lines == batch_result.total_lines
            assert batch_result.system_metrics.duration > 0

    def test_batch_cancel_with_csharp_executor_proxy(self):
        pass
