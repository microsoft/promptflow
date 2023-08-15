from collections import namedtuple
from types import GeneratorType
from unittest.mock import patch

import openai
import pytest

from promptflow._core.openai_injector import (
    PROMPTFLOW_PREFIX,
    USER_AGENT_HEADER,
    available_openai_apis,
    get_aoai_telemetry_headers,
    inject_openai_api,
    inject_operation_headers,
)
from promptflow._core.operation_context import OperationContext
from promptflow._core.tracer import Tracer
from promptflow._version import VERSION
from promptflow.connections import AzureOpenAIConnection
from promptflow.exceptions import UserErrorException
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.embedding import embedding


@pytest.mark.unittest
def test_inject_operation_headers():
    @inject_operation_headers
    def f(**kwargs):
        return kwargs

    injected_headers = get_aoai_telemetry_headers()
    assert f(a=1, b=2) == {"a": 1, "b": 2, "headers": injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2}
    assert f(headers={"a": 1, "b": 2}) == {"headers": merged_headers}

    aoai_tools_headers = injected_headers.copy()
    aoai_tools_headers.update({"ms-azure-ai-promptflow-called-from": "aoai-tool"})
    assert f(headers={"ms-azure-ai-promptflow-called-from": "aoai-tool"}) == {"headers": aoai_tools_headers}


@pytest.mark.unittest
def test_aoai_generator_proxy():
    def mock_aoai(**kwargs):
        # check if args has a stream parameter
        if "stream" in kwargs and kwargs["stream"]:
            # stream parameter is true, yield a string
            def generator():
                yield "This is a yielded string"

            return generator()
        else:
            # stream parameter is false or not given, return a string
            return "This is a returned string"

    with patch("openai.Completion.create", new=mock_aoai), patch("openai.ChatCompletion.create", new=mock_aoai), patch(
        "openai.Embedding.create", new=mock_aoai
    ):
        Tracer.start_tracing("mock_run_id")
        inject_openai_api()

        return_string = openai.Completion.create(stream=False)
        assert return_string == "This is a returned string"

        return_generator = openai.Completion.create(stream=True)
        assert isinstance(return_generator, GeneratorType)

        for _ in return_generator:
            pass

        traces = Tracer.end_tracing()
        assert len(traces) == 2
        for trace in traces:
            assert trace["type"] == "LLM"
            if trace["inputs"]["stream"]:
                assert trace["output"] == ["This is a yielded string"]
            else:
                assert trace["output"] == "This is a returned string"


@pytest.mark.unittest
def test_aoai_call_inject():
    def mock_aoai(**kwargs):
        return kwargs.get("headers")

    with patch("openai.Completion.create", new=mock_aoai), patch("openai.ChatCompletion.create", new=mock_aoai), patch(
        "openai.Embedding.create", new=mock_aoai
    ):
        inject_openai_api()
        injected_headers = get_aoai_telemetry_headers()

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


@pytest.mark.unittest
def test_get_aoai_telemetry_headers():
    # create a mock operation context
    mock_operation_context = OperationContext()
    mock_operation_context.user_agent = "test-user-agent"
    mock_operation_context.update(
        {
            "flow_id": "test-flow-id",
            "root_run_id": "test-root-run-id",
            "index": 1,
            "run_id": "test-run-id",
            "variant_id": "test-variant-id",
        }
    )

    # patch the OperationContext.get_instance method to return the mock operation context
    with patch("promptflow.core.operation_context.OperationContext.get_instance") as mock_get_instance:
        mock_get_instance.return_value = mock_operation_context

        # call the function under test and get the headers
        headers = get_aoai_telemetry_headers()

        for key in headers.keys():
            assert key.startswith(PROMPTFLOW_PREFIX) or key == USER_AGENT_HEADER
            assert "_" not in key

        # assert that the headers are correct
        assert headers[USER_AGENT_HEADER] == f"promptflow/{VERSION} test-user-agent"
        assert headers[f"{PROMPTFLOW_PREFIX}flow-id"] == "test-flow-id"
        assert headers[f"{PROMPTFLOW_PREFIX}root-run-id"] == "test-root-run-id"
        assert headers[f"{PROMPTFLOW_PREFIX}index"] == "1"
        assert headers[f"{PROMPTFLOW_PREFIX}run-id"] == "test-run-id"
        assert headers[f"{PROMPTFLOW_PREFIX}variant-id"] == "test-variant-id"
