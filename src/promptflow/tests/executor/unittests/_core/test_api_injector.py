from collections import namedtuple
from importlib.metadata import version
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

IS_LEGACY_OPENAI = version("openai").startswith("0.")


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
def test_aoai_generator_proxy_sync():
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

    if IS_LEGACY_OPENAI:
        apis = ["openai.Completion.create", "openai.ChatCompletion.create", "openai.Embedding.create"]
    else:
        apis = [
            "openai.resources.Completions.create",
            "openai.resources.chat.Completions.create",
            "openai.resources.Embeddings.create",
        ]

    with patch(apis[0], new=mock_aoai), patch(apis[1], new=mock_aoai), patch(apis[2], new=mock_aoai):
        Tracer.start_tracing("mock_run_id")
        inject_openai_api()

        if IS_LEGACY_OPENAI:
            return_string = openai.Completion.create(stream=False)
            return_generator = openai.Completion.create(stream=True)
        else:
            return_string = openai.resources.Completions.create(stream=False)
            return_generator = openai.resources.Completions.create(stream=True)

        assert return_string == "This is a returned string"
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
@pytest.mark.asyncio
async def test_aoai_generator_proxy_async():
    async def mock_aoai(**kwargs):
        # check if args has a stream parameter
        if "stream" in kwargs and kwargs["stream"]:
            # stream parameter is true, yield a string
            def generator():
                yield "This is a yielded string"

            return generator()
        else:
            # stream parameter is false or not given, return a string
            return "This is a returned string"

    if IS_LEGACY_OPENAI:
        apis = ["openai.Completion.acreate", "openai.ChatCompletion.acreate", "openai.Embedding.acreate"]
    else:
        apis = [
            "openai.resources.AsyncCompletions.create",
            "openai.resources.chat.AsyncCompletions.create",
            "openai.resources.AsyncEmbeddings.create",
        ]

    with patch(apis[0], new=mock_aoai), patch(apis[1], new=mock_aoai), patch(apis[2], new=mock_aoai):
        Tracer.start_tracing("mock_run_id")
        inject_openai_api()

        if IS_LEGACY_OPENAI:
            return_string = await openai.Completion.acreate(stream=False)
            return_generator = await openai.Completion.acreate(stream=True)
        else:
            return_string = await openai.resources.AsyncCompletions.create(stream=False)
            return_generator = await openai.resources.AsyncCompletions.create(stream=True)

        assert return_string == "This is a returned string"
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


@pytest.mark.parametrize(
    "removed_api, expected_apis",
    [
        (None, {"completions", "chat.completions", "embeddings"}),
        ("chat.Completions", {"completions", "embeddings"}),
        ("Embeddings", {"completions", "chat.completions"}),
    ],
)
def test_availabe_openai_apis(removed_api, expected_apis):
    def validate_api_set(expected_apis):
        available_apis = available_openai_apis()
        generated_apis = set()
        for api in available_apis:
            assert hasattr(api, "create")
            generated_apis.add(f"{api.__module__[17:]}")
        print(generated_apis)
        assert generated_apis == expected_apis

    if removed_api:
        with patch(f"openai.resources.{removed_api}", new=None):
            validate_api_set(expected_apis)
    else:
        validate_api_set(expected_apis)


@pytest.mark.skipif(not IS_LEGACY_OPENAI, reason="Skip on openai>=1.0.0")
@pytest.mark.parametrize(
    "removed_api, expected_apis",
    [
        (None, {"Completion", "ChatCompletion", "Embedding"}),
        ("ChatCompletion", {"Completion", "Embedding"}),
        ("Embedding", {"Completion", "ChatCompletion"}),
    ],
)
def test_availabe_openai_apis_for_legacy_openai(removed_api, expected_apis):
    def validate_api_set(expected_apis):
        available_apis = available_openai_apis()
        generated_apis = set()
        for api in available_apis:
            assert hasattr(api, "create")
            generated_apis.add(f"{api.__name__}")
        print(generated_apis)
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
    with patch("promptflow._core.operation_context.OperationContext.get_instance") as mock_get_instance:
        mock_get_instance.return_value = mock_operation_context

        # call the function under test and get the headers
        headers = get_aoai_telemetry_headers()

        for key in headers.keys():
            assert key.startswith(PROMPTFLOW_PREFIX) or key == USER_AGENT_HEADER
            assert "_" not in key

        # assert that the headers are correct
        assert headers[USER_AGENT_HEADER] == f"test-user-agent promptflow/{VERSION}"
        assert headers[f"{PROMPTFLOW_PREFIX}flow-id"] == "test-flow-id"
        assert headers[f"{PROMPTFLOW_PREFIX}root-run-id"] == "test-root-run-id"
        assert headers[f"{PROMPTFLOW_PREFIX}index"] == "1"
        assert headers[f"{PROMPTFLOW_PREFIX}run-id"] == "test-run-id"
        assert headers[f"{PROMPTFLOW_PREFIX}variant-id"] == "test-variant-id"
