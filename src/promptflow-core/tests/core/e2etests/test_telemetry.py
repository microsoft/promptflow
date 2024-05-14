import json
from collections import namedtuple
from importlib.metadata import version
from unittest.mock import patch

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.tracing._operation_context import OperationContext

from ...utils import get_yaml_file

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
