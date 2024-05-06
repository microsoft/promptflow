import json
import uuid
from collections import namedtuple
from importlib.metadata import version
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.tracing._operation_context import OperationContext

from ..process_utils import override_process_pool_targets
from ..utils import get_flow_folder, get_flow_inputs_file, get_yaml_file, load_jsonl

IS_LEGACY_OPENAI = version("openai").startswith("0.")


Completion = namedtuple("Completion", ["choices"])
Choice = namedtuple("Choice", ["message"])
Message = namedtuple("Message", ["content"])
Delta = namedtuple("Delta", ["content"])


def mock_chat(*args, **kwargs):
    if IS_LEGACY_OPENAI:
        message = Message(content=json.dumps(kwargs.get("headers", {})))
        return Completion(choices=[{"message": message}])
    else:
        message = Message(content=json.dumps(kwargs.get("extra_headers", {})))
        return Completion(choices=[Choice(message=message)])


def setup_mocks():
    patch_targets = {
        "openai.ChatCompletion.create": mock_chat,
        "openai.resources.chat.Completions.create": mock_chat,
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
        with patch(api, new=mock_chat):
            flow_folder = "openai_chat_api_flow"

            # flow run case
            operation_context = OperationContext.get_instance()
            operation_context.clear()
            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"

            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
            inputs = {"question": "What's your name?", "chat_history": [], "stream": False}
            flow_result = executor.exec_line(inputs)

            assert isinstance(flow_result.output, dict)
            headers = json.loads(flow_result.output.get("answer", ""))
            assert "promptflow/" in headers.get("x-ms-useragent")
            # User-defined properties `scenario` is not set in headers
            promptflow_headers = json.loads(headers.get("ms-azure-ai-promptflow"))
            assert "ms-azure-ai-promptflow-scenario" not in promptflow_headers
            assert promptflow_headers.get("run_mode") == RunMode.Test.name
            assert promptflow_headers.get("flow_id") == flow_result.run_info.flow_id
            assert promptflow_headers.get("root_run_id") == flow_result.run_info.run_id

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
            promptflow_headers = json.loads(headers.get("ms-azure-ai-promptflow"))
            assert "ms-azure-ai-promptflow-scenario" not in promptflow_headers
            assert promptflow_headers.get("run_mode") == RunMode.SingleNode.name

    def test_executor_openai_telemetry_with_batch_run(self, dev_connections, recording_injection):
        """This test validates telemetry info header is correctly injected to OpenAI API
        by mocking chat api method. The mock method will return a generator that yields a
        namedtuple with a json string of the headers passed to the method.
        """
        flow_folder = "openai_chat_api_flow"

        operation_context = OperationContext.get_instance()
        operation_context.clear()
        operation_context.set_default_tracing_keys({"default_dummy_key"})
        # Set user-defined properties `scenario` in context
        operation_context.scenario = "test"
        operation_context.dummy_key = "dummy_value"
        operation_context._tracking_keys.add("dummy_key")

        with override_process_pool_targets(mock_process_wrapper, mock_process_manager):
            run_id = str(uuid.uuid4())
            batch_engine = BatchEngine(
                get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
            )
            input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="non_stream_inputs.jsonl")}
            inputs_mapping = {"question": "${data.question}", "chat_history": "${data.chat_history}"}
            output_dir = Path(mkdtemp())
            bulk_result = batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id)

            assert isinstance(bulk_result, BatchResult)
            assert bulk_result.completed_lines == 2
            outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
            for line in outputs:
                headers = json.loads(line.get("answer", ""))
                assert "promptflow/" in headers.get("x-ms-useragent")
                promptflow_headers = json.loads(headers.get("ms-azure-ai-promptflow"))
                assert "ms-azure-ai-promptflow-scenario" not in promptflow_headers
                assert promptflow_headers.get("run_mode") == RunMode.Batch.name
                assert promptflow_headers.get("flow_id") == "default_flow_id"
                if not pytest.is_replay:
                    assert promptflow_headers.get("root_run_id") == run_id
                assert promptflow_headers.get("batch_input_source") == "Data"
                assert promptflow_headers.get("dummy_key") == "dummy_value"
