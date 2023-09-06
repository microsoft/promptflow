import json
import sys
import uuid
from collections import namedtuple
from unittest.mock import patch

import pytest

from promptflow._core.operation_context import OperationContext
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor

from ..utils import get_yaml_file

Completion = namedtuple("Completion", ["choices"])
Delta = namedtuple("Delta", ["content"])


def stream_response(kwargs):
    delta = Delta(content=json.dumps(kwargs.get("headers", {})))
    yield Completion(choices=[{"delta": delta}])


def mock_stream_chat(**kwargs):
    return stream_response(kwargs)


@pytest.mark.skipif(sys.platform == "darwin" or sys.platform == "win32", reason="Skip on Mac and Windows")
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

            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"
            executor = FlowExecutor.create(get_yaml_file("openai_api_flow"), dev_connections)

            # exec_line case
            inputs = {"question": "What's your name?", "chat_history": []}
            flow_result = executor.exec_line(inputs)

            assert isinstance(flow_result.output, dict)
            headers = json.loads(flow_result.output.get("answer", ""))

            assert "promptflow/" in headers.get("x-ms-useragent")
            assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
            assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Test.name

            # exec_bulk case
            run_id = str(uuid.uuid4())
            bulk_inputs = [inputs]
            bulk_result = executor.exec_bulk(bulk_inputs, run_id)

            for line in bulk_result.outputs:
                headers = json.loads(line.get("answer", ""))
                assert "promptflow/" in headers.get("x-ms-useragent")
                assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
                assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Batch.name

            # single_node case
            run_info = FlowExecutor.load_and_exec_node(
                get_yaml_file("openai_api_flow"),
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
