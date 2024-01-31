import json
import uuid
from collections import namedtuple
from importlib.metadata import version
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from promptflow._core.operation_context import OperationContext
from promptflow.batch._batch_engine import OUTPUT_FILE_NAME, BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager

from ..process_utils import enable_mock_in_process
from ..utils import get_flow_folder, get_flow_inputs_file, get_yaml_file, load_jsonl

IS_LEGACY_OPENAI = version("openai").startswith("0.")


Completion = namedtuple("Completion", ["choices"])
Choice = namedtuple("Choice", ["delta"])
Delta = namedtuple("Delta", ["content"])


def stream_response(kwargs):
    if IS_LEGACY_OPENAI:
        delta = Delta(content=json.dumps(kwargs.get("headers", {})))
        yield Completion(choices=[{"delta": delta}])
    else:
        delta = Delta(content=json.dumps(kwargs.get("extra_headers", {})))
        yield Completion(choices=[Choice(delta=delta)])


def mock_stream_chat(*args, **kwargs):
    return stream_response(kwargs)


def setup_mocks():
    patch_targets = {
        "openai.ChatCompletion.create": mock_stream_chat,
        "openai.resources.chat.Completions.create": mock_stream_chat,
    }
    for target, func in patch_targets.items():
        patcher = patch(target, func)
        patcher.start()


def mock_process_wrapper(*args, **kwargs):
    setup_mocks()
    _process_wrapper(*args, **kwargs)


def mock_process_manager(*args, **kwargs):
    setup_mocks()
    create_spawned_fork_process_manager(*args, **kwargs)


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorTelemetry:
    def test_executor_openai_telemetry(self, dev_connections):
        """This test validates telemetry info header is correctly injected to OpenAI API
        by mocking chat api method. The mock method will return a generator that yields a
        namedtuple with a json string of the headers passed to the method.
        """
        if IS_LEGACY_OPENAI:
            api = "openai.ChatCompletion.create"
        else:
            api = "openai.resources.chat.Completions.create"
        with patch(api, new=mock_stream_chat):
            flow_folder = "openai_chat_api_flow"

            # flow run case
            operation_context = OperationContext.get_instance()
            operation_context.clear()
            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"

            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
            inputs = {"question": "What's your name?", "chat_history": [], "stream": True}
            flow_result = executor.exec_line(inputs)

            assert isinstance(flow_result.output, dict)
            headers = json.loads(flow_result.output.get("answer", ""))
            assert "promptflow/" in headers.get("x-ms-useragent")
            assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
            assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Test.name
            assert headers.get("ms-azure-ai-promptflow-flow-id") == flow_result.run_info.flow_id
            assert headers.get("ms-azure-ai-promptflow-root-run-id") == flow_result.run_info.run_id

            # single_node case
            operation_context = OperationContext.get_instance()
            operation_context.clear()
            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"

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

    def test_executor_openai_telemetry_with_batch_run(self, dev_connections):
        """This test validates telemetry info header is correctly injected to OpenAI API
        by mocking chat api method. The mock method will return a generator that yields a
        namedtuple with a json string of the headers passed to the method.
        """
        flow_folder = "openai_chat_api_flow"

        operation_context = OperationContext.get_instance()
        operation_context.clear()
        # Set user-defined properties `scenario` in context
        operation_context.scenario = "test"

        with enable_mock_in_process(mock_process_wrapper, mock_process_manager):
            run_id = str(uuid.uuid4())
            batch_engine = BatchEngine(
                get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
            )
            input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="stream_inputs.jsonl")}
            inputs_mapping = {"question": "${data.question}", "chat_history": "${data.chat_history}"}
            output_dir = Path(mkdtemp())
            bulk_result = batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id)

            assert isinstance(bulk_result, BatchResult)
            assert bulk_result.completed_lines == 2
            outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
            for line in outputs:
                headers = json.loads(line.get("answer", ""))
                assert "promptflow/" in headers.get("x-ms-useragent")
                assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
                assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Batch.name
                assert headers.get("ms-azure-ai-promptflow-flow-id") == "default_flow_id"
                assert headers.get("ms-azure-ai-promptflow-root-run-id") == run_id
