import json
from collections import namedtuple
from importlib.metadata import version
from unittest.mock import patch

import openai
import pytest

from promptflow._core.operation_context import OperationContext
from promptflow._version import VERSION
from promptflow.connections import AzureOpenAIConnection
from promptflow.exceptions import UserErrorException
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.embedding import embedding
from promptflow.tracing._integrations._openai_injector import (
    PROMPTFLOW_HEADER,
    USER_AGENT_HEADER,
    get_aoai_telemetry_headers,
    inject_openai_api,
    inject_operation_headers,
)

IS_LEGACY_OPENAI = version("openai").startswith("0.")


# Mock classes and functions for test
class MockAPI:
    def create(self):
        pass


@pytest.mark.unittest
def test_inject_operation_headers_sync():
    @inject_operation_headers
    def f(**kwargs):
        return kwargs

    if IS_LEGACY_OPENAI:
        headers = "headers"
        kwargs_1 = {"headers": {"a": 1, "b": 2}}
        kwargs_2 = {"headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}
    else:
        headers = "extra_headers"
        kwargs_1 = {"extra_headers": {"a": 1, "b": 2}}
        kwargs_2 = {"extra_headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}

    injected_headers = get_aoai_telemetry_headers()
    assert f(a=1, b=2) == {"a": 1, "b": 2, headers: injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2}
    assert f(**kwargs_1) == {headers: merged_headers}

    aoai_tools_headers = injected_headers.copy()
    aoai_tools_headers.update({"ms-azure-ai-promptflow-called-from": "aoai-tool"})
    assert f(**kwargs_2) == {headers: aoai_tools_headers}


@pytest.mark.unittest
@pytest.mark.asyncio
async def test_inject_operation_headers_async():
    @inject_operation_headers
    async def f(**kwargs):
        return kwargs

    if IS_LEGACY_OPENAI:
        headers = "headers"
        kwargs_1 = {"headers": {"a": 1, "b": 2}}
        kwargs_2 = {"headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}
    else:
        headers = "extra_headers"
        kwargs_1 = {"extra_headers": {"a": 1, "b": 2}}
        kwargs_2 = {"extra_headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}

    injected_headers = get_aoai_telemetry_headers()
    assert await f(a=1, b=2) == {"a": 1, "b": 2, headers: injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2}
    assert await f(**kwargs_1) == {headers: merged_headers}

    aoai_tools_headers = injected_headers.copy()
    aoai_tools_headers.update({"ms-azure-ai-promptflow-called-from": "aoai-tool"})
    assert await f(**kwargs_2) == {headers: aoai_tools_headers}


@pytest.mark.unittest
def test_aoai_call_inject():
    if IS_LEGACY_OPENAI:
        headers = "headers"
        apis = ["openai.Completion.create", "openai.ChatCompletion.create", "openai.Embedding.create"]
    else:
        headers = "extra_headers"
        apis = [
            "openai.resources.Completions.create",
            "openai.resources.chat.Completions.create",
            "openai.resources.Embeddings.create",
        ]

    def mock_aoai(**kwargs):
        return kwargs.get(headers)

    with patch(apis[0], new=mock_aoai), patch(apis[1], new=mock_aoai), patch(apis[2], new=mock_aoai):
        inject_openai_api()
        injected_headers = get_aoai_telemetry_headers()

        if IS_LEGACY_OPENAI:
            return_headers_1 = openai.Completion.create(headers=None)
            return_headers_2 = openai.ChatCompletion.create(headers="abc")
            return_headers_3 = openai.Embedding.create(headers=1)
        else:
            return_headers_1 = openai.resources.Completions.create(extra_headers=None)
            return_headers_2 = openai.resources.chat.Completions.create(extra_headers="abc")
            return_headers_3 = openai.resources.Embeddings.create(extra_headers=1)

        assert return_headers_1 is not None
        assert injected_headers.items() <= return_headers_1.items()

        assert return_headers_2 is not None
        assert injected_headers.items() <= return_headers_2.items()

        assert return_headers_3 is not None
        assert injected_headers.items() <= return_headers_3.items()


@pytest.mark.unittest
def test_aoai_tool_header():
    def mock_complete(*args, **kwargs):
        Response = namedtuple("Response", ["choices"])
        Choice = namedtuple("Choice", ["text"])
        choice = Choice(text=kwargs.get("extra_headers", {}))
        response = Response(choices=[choice])
        return response

    def mock_chat(*args, **kwargs):
        Completion = namedtuple("Completion", ["choices"])
        Choice = namedtuple("Choice", ["message"])
        Message = namedtuple("Message", ["content"])
        message = Message(content=kwargs.get("extra_headers", {}))
        choice = Choice(message=message)
        completion = Completion(choices=[choice])
        return completion

    def mock_embedding(*args, **kwargs):
        Response = namedtuple("Response", ["data"])
        Embedding = namedtuple("Embedding", ["embedding"])
        response = Response(data=[Embedding(embedding=kwargs.get("extra_headers", {}))])
        return response

    with patch("openai.resources.Completions.create", new=mock_complete), patch(
        "openai.resources.chat.Completions.create", new=mock_chat
    ), patch("openai.resources.Embeddings.create", new=mock_embedding):
        inject_openai_api()
        aoai_tool_header = {"ms-azure-ai-promptflow-called-from": "aoai-tool"}

        return_headers = AzureOpenAI(AzureOpenAIConnection(api_key="test", api_base="test")).completion(
            prompt="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

        return_headers = AzureOpenAI(AzureOpenAIConnection(api_key="test", api_base="test")).chat(
            prompt="user:\ntest", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

        return_headers = embedding(
            AzureOpenAIConnection(api_key="test", api_base="test"), input="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()


@pytest.mark.unittest
def test_aoai_chat_tool_prompt():
    def mock_chat(*args, **kwargs):
        Completion = namedtuple("Completion", ["choices"])
        Choice = namedtuple("Choice", ["message"])
        Message = namedtuple("Message", ["content"])
        message = Message(content=kwargs.get("messages", {}))
        choice = Choice(message=message)
        completion = Completion(choices=[choice])
        return completion

    with patch("openai.resources.chat.Completions.create", new=mock_chat):
        inject_openai_api()
        return_messages = AzureOpenAI(AzureOpenAIConnection(api_key="test", api_base="test")).chat(
            prompt="user:\ntest", deployment_name="test"
        )
        assert return_messages == [{"role": "user", "content": "test"}]

        return_messages = AzureOpenAI(AzureOpenAIConnection(api_key="test", api_base="test")).chat(
            prompt="user:\r\n", deployment_name="test"
        )
        assert return_messages == [{"role": "user", "content": ""}]

        with pytest.raises(UserErrorException, match="The Chat API requires a specific format for prompt"):
            AzureOpenAI(AzureOpenAIConnection(api_key="test", api_base="test")).chat(
                prompt="user:", deployment_name="test"
            )


@pytest.mark.unittest
def test_get_aoai_telemetry_headers():
    # create a mock operation context
    mock_operation_context = OperationContext.get_instance()
    mock_operation_context.user_agent = "test-user-agent"
    mock_operation_context.update(
        {
            "flow_id": "test-flow-id",
            "root_run_id": "test-root-run-id",
        }
    )

    # patch the OperationContext.get_instance method to return the mock operation context
    with patch("promptflow._core.operation_context.OperationContext.get_instance") as mock_get_instance:
        mock_get_instance.return_value = mock_operation_context

        # call the function under test and get the headers
        headers = get_aoai_telemetry_headers()

        assert USER_AGENT_HEADER in headers
        assert PROMPTFLOW_HEADER in headers

        for key in headers.keys():
            assert "_" not in key

        # assert that the headers are correct
        assert headers[USER_AGENT_HEADER] == f"test-user-agent promptflow/{VERSION}"
        promptflow_headers = json.loads(headers[PROMPTFLOW_HEADER])
        assert promptflow_headers["flow_id"] == "test-flow-id"
        assert promptflow_headers["root_run_id"] == "test-root-run-id"

        context = OperationContext.get_instance()
        context.dummy_key = "dummy_value"
        headers = get_aoai_telemetry_headers()
        promptflow_headers = json.loads(headers[PROMPTFLOW_HEADER])
        assert "dummy_key" not in promptflow_headers  # not default telemetry

        context._tracking_keys.add("dummy_key")
        headers = get_aoai_telemetry_headers()
        promptflow_headers = json.loads(headers[PROMPTFLOW_HEADER])
        assert promptflow_headers["dummy_key"] == "dummy_value"  # telemetry key inserted
