import pkg_resources
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.executor._result import BatchResult, LineResult

from ..utils import get_flow_folder, get_flow_inputs_file, get_yaml_file


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
        if flow_folder.startswith("openai"):
            if pkg_resources.get_distribution("openai").version.startswith("1."):
                pytest.skip("test needs to be upgraded to adapt to openai>=1.0.0")
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert isinstance(batch_results, BatchResult)
        for _, line_result in enumerate(batch_results.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed
        openai_metrics = batch_results.get_openai_metrics()
        assert "completion_tokens" in openai_metrics
        assert "prompt_tokens" in openai_metrics
        assert "total_tokens" in openai_metrics
        assert openai_metrics["total_tokens"] > 0
