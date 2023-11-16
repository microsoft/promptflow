import json
import uuid
from collections import namedtuple
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from promptflow._core.operation_context import OperationContext
from promptflow.batch import BatchEngine
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor

from ..utils import get_flow_folder, get_flow_inputs_file, get_yaml_file

Completion = namedtuple("Completion", ["choices"])
Delta = namedtuple("Delta", ["content"])


def stream_response(kwargs):
    delta = Delta(content=json.dumps(kwargs.get("headers", {})))
    yield Completion(choices=[{"delta": delta}])


def mock_stream_chat(**kwargs):
    return stream_response(kwargs)


# @pytest.mark.skipif(sys.platform == "darwin" or sys.platform == "win32", reason="Skip on Mac and Windows")
@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorTelemetry:
    def test_executor_openai_telemetry(self, dev_connections):
        """This test validates telemetry info header is correctly injected to OpenAI API
        by mocking openai.ChatCompletion.create method. The mock method will return a generator
        that yields a namedtuple with a json string of the headers passed to the method.
        """

        with patch("openai.ChatCompletion.create", new=mock_stream_chat):
            operation_context = OperationContext.get_instance()
            operation_context.clear()

            flow_folder = "openai_chat_api_flow"
            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)

            # flow run case
            inputs = {"question": "What's your name?", "chat_history": []}
            flow_result = executor.exec_line(inputs)

            assert isinstance(flow_result.output, dict)
            headers = json.loads(flow_result.output.get("answer", ""))

            assert "promptflow/" in headers.get("x-ms-useragent")
            assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
            assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Test.name

            # batch run case
            run_id = str(uuid.uuid4())
            batch_engine = BatchEngine(
                get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
            )
            input_dirs = {"data": get_flow_inputs_file(flow_folder)}
            inputs_mapping = {"question": "${data.question}", "chat_history": "${data.chat_history}"}
            output_dir = Path(mkdtemp())
            batch_result = batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id)

            for line in batch_result.outputs:
                headers = json.loads(line.get("answer", ""))
                assert "promptflow/" in headers.get("x-ms-useragent")
                assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
                assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Batch.name

            # single_node case
            run_info = FlowExecutor.load_and_exec_node(
                get_yaml_file("openai_chat_api_flow"),
                "chat",
                flow_inputs=inputs,
                connections=dev_connections,
                raise_ex=True,
            )
            assert run_info.output is not None
            headers = json.loads(run_info.output)
            assert "promptflow/" in headers.get("x-ms-useragent")
            assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
            assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.SingleNode.name
