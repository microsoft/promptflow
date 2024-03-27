from collections import namedtuple
from importlib.metadata import version
from unittest.mock import patch

import pytest

from promptflow.connections import AzureOpenAIConnection
from promptflow.exceptions import UserErrorException
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.embedding import embedding
from promptflow.tracing._integrations._openai_injector import inject_openai_api

IS_LEGACY_OPENAI = version("openai").startswith("0.")


# Mock classes and functions for test
class MockAPI:
    def create(self):
        pass


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
