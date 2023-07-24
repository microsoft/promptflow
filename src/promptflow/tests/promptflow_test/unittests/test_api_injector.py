from collections import namedtuple
from unittest.mock import patch

import openai
import pytest

from promptflow.connections import AzureOpenAIConnection
from promptflow.core.api_injector import available_openai_apis, inject_openai_api, inject_operation_headers
from promptflow.core.operation_context import OperationContext
from promptflow.exceptions import UserErrorException
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.embedding import embedding


@pytest.mark.unittest
def test_inject_operation_headers():
    @inject_operation_headers
    def f(**kwargs):
        return kwargs

    injected_headers = OperationContext.get_instance().get_http_headers()
    assert f(a=1, b=2) == {"a": 1, "b": 2, "headers": injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2}
    assert f(headers={"a": 1, "b": 2}) == {"headers": merged_headers}

    conflict_headers = injected_headers.copy()
    conflict_headers.update({"ms-azure-ai-promptflow-called-from": "aoai-tool"})
    assert f(headers={"ms-azure-ai-promptflow-called-from": "aoai-tool"}) == {"headers": conflict_headers}


@pytest.mark.unittest
def test_aoai_call_inject():
    def mock_aoai(**kwargs):
        return kwargs.get("headers")

    with patch("openai.Completion.create", new=mock_aoai), patch("openai.ChatCompletion.create", new=mock_aoai), patch(
        "openai.Embedding.create", new=mock_aoai
    ):
        inject_openai_api()
        injected_headers = OperationContext.get_instance().get_http_headers()

        return_headers = openai.Completion.create(headers=None)
        assert return_headers is not None
        assert injected_headers.items() <= return_headers.items()

        return_headers = openai.ChatCompletion.create(headers="abc")
        assert return_headers is not None
        assert injected_headers.items() <= return_headers.items()

        return_headers = openai.Embedding.create(headers=1)
        assert return_headers is not None
        assert injected_headers.items() <= return_headers.items()


@pytest.mark.unittest
def test_aoai_tool_header():
    def mock_complete(**kwargs):
        Response = namedtuple("Response", ["choices"])
        Choice = namedtuple("Choice", ["text"])
        choice = Choice(text=kwargs.get("headers", {}))
        response = Response(choices=[choice])
        return response

    def mock_chat(**kwargs):
        Completion = namedtuple("Completion", ["choices"])
        Choice = namedtuple("Choice", ["message"])
        Message = namedtuple("Message", ["content"])
        message = Message(content=kwargs.get("headers", {}))
        choice = Choice(message=message)
        completion = Completion(choices=[choice])
        return completion

    def mock_embedding(**kwargs):
        response = {"data": [{"embedding": kwargs.get("headers", {})}]}
        return response

    with patch("openai.Completion.create", new=mock_complete), patch(
        "openai.ChatCompletion.create", new=mock_chat
    ), patch("openai.Embedding.create", new=mock_embedding):
        inject_openai_api()
        aoai_tool_header = {"ms-azure-ai-promptflow-called-from": "aoai-tool"}

        return_headers = AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).completion(
            prompt="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

        return_headers = AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).chat(
            prompt="user:\ntest", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

        return_headers = AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).embedding(
            input="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

        return_headers = embedding(
            AzureOpenAIConnection(api_key=None, api_base=None), input="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()

    with patch("openai.Embedding.create", new=mock_embedding):
        inject_openai_api()
        aoai_tool_header = {"ms-azure-ai-promptflow-called-from": "aoai-tool"}

        return_headers = embedding(
            AzureOpenAIConnection(api_key=None, api_base=None), input="test", deployment_name="test"
        )
        assert aoai_tool_header.items() <= return_headers.items()


@pytest.mark.unittest
def test_aoai_chat_tool_prompt():
    def mock_chat(**kwargs):
        Completion = namedtuple("Completion", ["choices"])
        Choice = namedtuple("Choice", ["message"])
        Message = namedtuple("Message", ["content"])
        message = Message(content=kwargs.get("messages", {}))
        choice = Choice(message=message)
        completion = Completion(choices=[choice])
        return completion

    with patch("openai.ChatCompletion.create", new=mock_chat):
        inject_openai_api()
        return_messages = AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).chat(
            prompt="user:\ntest", deployment_name="test"
        )
        assert return_messages == [{"role": "user", "content": "test"}]

        return_messages = AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).chat(
            prompt="user:\r\n", deployment_name="test"
        )
        assert return_messages == [{"role": "user", "content": ""}]

        with pytest.raises(UserErrorException, match="The Chat API requires a specific format for prompt"):
            AzureOpenAI(AzureOpenAIConnection(api_key=None, api_base=None)).chat(prompt="user:", deployment_name="test")


@pytest.mark.parametrize(
    "removed_api, expected_apis",
    [
        (None, {"Completion", "ChatCompletion", "Embedding"}),
        ("ChatCompletion", {"Completion", "Embedding"}),
        ("Embedding", {"Completion", "ChatCompletion"}),
    ],
)
def test_availabe_openai_apis(removed_api, expected_apis):
    def validate_api_set(expected_apis):
        available_apis = available_openai_apis()
        generated_apis = set()
        for api in available_apis:
            assert hasattr(api, "create")
            generated_apis.add(api.__name__)
        assert generated_apis == expected_apis

    if removed_api:
        with patch(f"openai.{removed_api}", new=None):
            validate_api_set(expected_apis)
    else:
        validate_api_set(expected_apis)
