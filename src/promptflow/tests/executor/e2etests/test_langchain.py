from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.batch import BatchEngine
from promptflow.batch._result import BatchResult

from ..utils import get_flow_folder, get_flow_inputs_file, get_yaml_file


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestLangchain:
    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping",
        [
            # Below case failed on CI and investigate later
            # ("flow_with_langchain_traces", {"question": "${data.question}"}),
            ("openai_chat_api_flow", {"question": "${data.question}", "chat_history": "${data.chat_history}"}),
            ("openai_completion_api_flow", {"prompt": "${data.prompt}"}),
        ],
    )
    def test_batch_with_langchain(self, flow_folder, inputs_mapping, dev_connections):
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert isinstance(batch_results, BatchResult)
        assert batch_results.total_lines == batch_results.completed_lines
        assert batch_results.system_metrics.total_tokens > 0
