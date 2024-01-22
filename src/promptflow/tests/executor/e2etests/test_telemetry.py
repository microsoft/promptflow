import json
import uuid
from asyncio import Queue
from collections import namedtuple
from importlib.metadata import version
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from promptflow._core.operation_context import OperationContext
from promptflow.batch._batch_engine import OUTPUT_FILE_NAME, BatchEngine
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager

from ..conftest import override_process_target
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


def setup_extra_mocks():
    patch_targets = ["openai.ChatCompletion.create", "openai.resources.chat.Completions.create"]
    patches = []
    for target in patch_targets:
        patcher = patch(target, mock_stream_chat)
        patches.append(patcher)
        patcher.start()
    return patches


def _customized_mock_process_wrapper(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func,
    operation_contexts_dict: dict,
):
    setup_extra_mocks()
    _process_wrapper(
        executor_creation_func, input_queue, output_queue, log_context_initialization_func, operation_contexts_dict
    )


def _customized_mock_create_spawned_fork_process_manager(
    log_context_initialization_func,
    current_operation_context,
    input_queues,
    output_queues,
    control_signal_queue,
    flow_file,
    connections,
    working_dir,
    raise_ex,
    process_info,
    process_target_func,
):
    setup_extra_mocks()
    create_spawned_fork_process_manager(
        log_context_initialization_func,
        current_operation_context,
        input_queues,
        output_queues,
        control_signal_queue,
        flow_file,
        connections,
        working_dir,
        raise_ex,
        process_info,
        process_target_func,
    )


def mock_stream_chat(*args, **kwargs):
    return stream_response(kwargs)


@pytest.mark.usefixtures("dev_connections", "recording_injection")
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
            operation_context = OperationContext.get_instance()
            operation_context.clear()

            flow_folder = "openai_chat_api_flow"
            # Set user-defined properties `scenario` in context
            operation_context.scenario = "test"
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)

            # flow run case
            inputs = {"question": "What's your name?", "chat_history": [], "stream": True}
            flow_result = executor.exec_line(inputs)

            assert isinstance(flow_result.output, dict)
            headers = json.loads(flow_result.output.get("answer", ""))

            assert "promptflow/" in headers.get("x-ms-useragent")
            assert headers.get("ms-azure-ai-promptflow-scenario") == "test"
            assert headers.get("ms-azure-ai-promptflow-run-mode") == RunMode.Test.name

            # batch run case
            # override the _process_wrapper with a customized one to mock the chat api
            with override_process_target(
                process_wrapper=_customized_mock_process_wrapper,
                process_manager=_customized_mock_create_spawned_fork_process_manager,
            ):
                run_id = str(uuid.uuid4())
                batch_engine = BatchEngine(
                    get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
                )
                input_dirs = {"data": get_flow_inputs_file(flow_folder)}
                inputs_mapping = {"question": "${data.question}", "chat_history": "${data.chat_history}"}
                output_dir = Path(mkdtemp())
                batch_engine.run(input_dirs, inputs_mapping, output_dir, run_id=run_id)

                outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
                for line in outputs:
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
