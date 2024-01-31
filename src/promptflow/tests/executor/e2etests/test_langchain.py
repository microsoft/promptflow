from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.batch import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_info import Status

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file


def validate_traces(api_call: dict) -> bool:
    name = api_call.get("name", "")
    if name in [
        "openai.resources.chat.completions.Completions.create",
        "openai.resources.completions.Completions.create"
    ]:
        return True
    for child in api_call.get("children", []):
        if validate_traces(child):
            return True
    return False


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestLangchain:
    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            ("flow_with_langchain_traces", {"question": "${data.question}"}),
            ("openai_chat_api_flow", {"question": "${data.question}", "chat_history": "${data.chat_history}"}),
            ("openai_completion_api_flow", {"prompt": "${data.prompt}"}),
        ],
    )
    def test_batch_with_langchain(self, flow_folder, inputs_mapping, dev_connections):
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=mem_run_storage
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert isinstance(batch_results, BatchResult)
        assert batch_results.total_lines == batch_results.completed_lines
        assert batch_results.system_metrics.total_tokens > 0
        for run_info in mem_run_storage._flow_runs.values():
            assert run_info.status == Status.Completed
            assert run_info.api_calls
            assert all([validate_traces(api_call) for api_call in run_info.api_calls])
        for run_info in mem_run_storage._node_runs.values():
            assert run_info.status == Status.Completed
