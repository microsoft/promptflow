import json
import logging
from collections.abc import AsyncIterator, Iterator
from importlib.metadata import version
from unittest.mock import MagicMock, patch

import openai
import pytest

from promptflow.tracing._integrations._openai_injector import (
    PROMPTFLOW_HEADER,
    USER_AGENT_HEADER,
    _generate_api_and_injector,
    _legacy_openai_apis,
    _openai_api_list,
    _openai_apis,
    get_aoai_telemetry_headers,
    inject_async,
    inject_openai_api,
    inject_operation_headers,
    inject_sync,
    recover_openai_api,
)
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._tracer import Tracer
from promptflow.tracing._version import VERSION
from promptflow.tracing.contracts.trace import TraceType

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
        kwargs_1 = {"headers": {"a": 1, "b": 2, "x-ms-useragent": "user_agent_test"}}
        kwargs_2 = {"headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}
    else:
        headers = "extra_headers"
        kwargs_1 = {"extra_headers": {"a": 1, "b": 2, "x-ms-useragent": "user_agent_test"}}
        kwargs_2 = {"extra_headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}

    injected_headers = get_aoai_telemetry_headers()
    user_agent = injected_headers.get("x-ms-useragent", None)
    assert user_agent is not None
    assert f(a=1, b=2) == {"a": 1, "b": 2, headers: injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2, "x-ms-useragent": " ".join([user_agent, "user_agent_test"])}
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
        kwargs_1 = {"headers": {"a": 1, "b": 2, "x-ms-useragent": "user_agent_test"}}
        kwargs_2 = {"headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}
    else:
        headers = "extra_headers"
        kwargs_1 = {"extra_headers": {"a": 1, "b": 2, "x-ms-useragent": "user_agent_test"}}
        kwargs_2 = {"extra_headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}}

    injected_headers = get_aoai_telemetry_headers()
    user_agent = injected_headers.get("x-ms-useragent", None)
    assert user_agent is not None
    assert await f(a=1, b=2) == {"a": 1, "b": 2, headers: injected_headers}

    merged_headers = {**injected_headers, "a": 1, "b": 2, "x-ms-useragent": " ".join([user_agent, "user_agent_test"])}
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
def test_get_aoai_telemetry_headers():
    # create a mock operation context
    mock_operation_context = OperationContext.get_instance()
    mock_operation_context.set_default_tracing_keys({"flow_id", "root_run_id"})
    mock_operation_context.user_agent = "test-user-agent"
    mock_operation_context.update(
        {
            "flow_id": "test-flow-id",
            "root_run_id": "test-root-run-id",
        }
    )

    # patch the OperationContext.get_instance method to return the mock operation context
    with patch("promptflow.tracing._operation_context.OperationContext.get_instance") as mock_get_instance:
        mock_get_instance.return_value = mock_operation_context

        # call the function under test and get the headers
        headers = get_aoai_telemetry_headers()

        assert USER_AGENT_HEADER in headers
        assert PROMPTFLOW_HEADER in headers

        for key in headers.keys():
            assert "_" not in key

        # assert that the headers are correct
        ua = f"test-user-agent promptflow-tracing/{VERSION}"
        assert headers[USER_AGENT_HEADER] == ua
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


@pytest.mark.unittest
def test_openai_generator_proxy_sync():
    def mock_openai(**kwargs):
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

    with patch(apis[0], new=mock_openai), patch(apis[1], new=mock_openai), patch(apis[2], new=mock_openai):
        Tracer.start_tracing("mock_run_id")
        inject_openai_api()

        if IS_LEGACY_OPENAI:
            return_string = openai.Completion.create(stream=False)
            return_generator = openai.Completion.create(stream=True)
        else:
            return_string = openai.resources.Completions.create(stream=False)
            return_generator = openai.resources.Completions.create(stream=True)

        assert return_string == "This is a returned string"
        assert isinstance(return_generator, Iterator)

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
async def test_openai_generator_proxy_async():
    async def mock_openai(**kwargs):
        # check if args has a stream parameter
        if "stream" in kwargs and kwargs["stream"]:
            # stream parameter is true, yield a string
            async def generator():
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

    with patch(apis[0], new=mock_openai), patch(apis[1], new=mock_openai), patch(apis[2], new=mock_openai):
        Tracer.start_tracing("mock_run_id")
        inject_openai_api()

        if IS_LEGACY_OPENAI:
            return_string = await openai.Completion.acreate(stream=False)
            return_generator = await openai.Completion.acreate(stream=True)
        else:
            return_string = await openai.resources.AsyncCompletions.create(stream=False)
            return_generator = await openai.resources.AsyncCompletions.create(stream=True)

        assert return_string == "This is a returned string"
        assert isinstance(return_generator, AsyncIterator)

        async for _ in return_generator:
            pass

        traces = Tracer.end_tracing()
        assert len(traces) == 2
        for trace in traces:
            assert trace["type"] == "LLM"
            if trace["inputs"]["stream"]:
                assert trace["output"] == ["This is a yielded string"]
            else:
                assert trace["output"] == "This is a returned string"


# The new generator-based test function
@pytest.mark.parametrize(
    "is_legacy, expected_apis_with_injectors",
    [
        (
            False,
            [
                (
                    _openai_apis()[0],
                    inject_sync,
                ),
                (
                    _openai_apis()[1],
                    inject_async,
                ),
            ],
        ),
        (
            True,
            [
                (
                    _legacy_openai_apis()[0],
                    inject_sync,
                ),
                (
                    _legacy_openai_apis()[1],
                    inject_async,
                ),
            ],
        ),
    ],
)
def test_api_list(is_legacy, expected_apis_with_injectors):
    with patch("promptflow.tracing._integrations._openai_injector.IS_LEGACY_OPENAI", is_legacy):
        # Using list comprehension to get all items from the generator
        actual_apis_with_injectors = list(_openai_api_list())
        # Assert that the actual list matches the expected list
        assert actual_apis_with_injectors == expected_apis_with_injectors


@pytest.mark.parametrize(
    "apis_with_injectors, expected_output, expected_logs",
    [
        (
            [((("MockModule", "MockAPI", "create", TraceType.LLM, "Mock.create"),), inject_sync)],
            [(MockAPI, "create", TraceType.LLM, inject_sync, "Mock.create")],
            [],
        ),
        (
            [((("MockModule", "MockAPI", "create", TraceType.LLM, "Mock.acreate"),), inject_async)],
            [(MockAPI, "create", TraceType.LLM, inject_async, "Mock.acreate")],
            [],
        ),
    ],
)
def test_generate_api_and_injector(apis_with_injectors, expected_output, expected_logs, caplog):
    with patch("importlib.import_module", return_value=MagicMock(MockAPI=MockAPI)) as mock_import_module:
        # Capture the logs
        with caplog.at_level(logging.WARNING):
            # Run the generator and collect the output
            result = list(_generate_api_and_injector(apis_with_injectors))

        # Check if the logs match the expected logs
        assert len(caplog.records) == len(expected_logs)
        for record, expected_message in zip(caplog.records, expected_logs):
            assert expected_message in record.message

        # Check if the result matches the expected output
        assert result == expected_output

    mock_import_module.assert_called_with("MockModule")


def test_generate_api_and_injector_attribute_error_logging(caplog):
    apis = [
        ((("NonExistentModule", "NonExistentAPI", "create", TraceType.LLM, "create"),), MagicMock()),
        (
            (
                (
                    "MockModuleMissingMethod",
                    "MockAPIMissingMethod",
                    "missing_method",
                    "missing_trace_type",
                    "missing_name",
                ),
            ),
            MagicMock(),
        ),
    ]

    # Set up the side effect for the mock
    def import_module_effect(name):
        if name == "MockModuleMissingMethod":
            module = MagicMock()
            delattr(module, "MockAPIMissingMethod")  # Use delattr to remove the attribute
            return module
        else:
            raise ModuleNotFoundError(f"No module named '{name}'")

    with patch("importlib.import_module") as mock_import_module:
        mock_import_module.side_effect = import_module_effect
        with caplog.at_level(logging.WARNING):
            list(_generate_api_and_injector(apis))

        assert len(caplog.records) == 2
        assert "An unexpected error occurred" in caplog.records[0].message
        assert "NonExistentModule" in caplog.records[0].message
        assert "does not have the class" in caplog.records[1].message
        assert "MockAPIMissingMethod" in caplog.records[1].message

    # Verify that `importlib.import_module` was called with correct module names
    mock_import_module.assert_any_call("NonExistentModule")
    mock_import_module.assert_any_call("MockModuleMissingMethod")


@pytest.mark.unittest
def test_inject_and_recover_openai_api():
    class FakeAPIWithoutOriginal:
        @staticmethod
        def create():
            pass

    class FakeAPIWithOriginal:
        @staticmethod
        def create():
            pass

    def dummy_api():
        pass

    # Real injector function that adds an _original attribute
    def injector(f, trace_type, name):
        def wrapper_fun(*args, **kwargs):
            return f(*args, **kwargs)

        wrapper_fun._original = f
        return wrapper_fun

    # Set an _original attribute for the create method of FakeAPIWithOriginal
    FakeAPIWithOriginal.create._original = dummy_api

    # Store the original create methods before injection
    original_api_without_original = FakeAPIWithoutOriginal.create
    original_api_with_original = FakeAPIWithOriginal.create

    # Mock the generator function to yield our mocked api and method
    with patch(
        "promptflow.tracing._integrations._openai_injector.available_openai_apis_and_injectors",
        return_value=[
            (FakeAPIWithoutOriginal, "create", TraceType.LLM, injector, "create"),
            (FakeAPIWithOriginal, "create", TraceType.LLM, injector, "create"),
        ],
    ):
        # Call the function to inject the APIs
        inject_openai_api()

        # Check that the _original attribute was set for the method that didn't have it
        assert hasattr(FakeAPIWithoutOriginal.create, "_original")
        # Ensure the _original attribute points to the correct original method
        assert FakeAPIWithoutOriginal.create._original is original_api_without_original

        # Check that the injector was not applied again to the method that already had an _original attribute
        # The _original attribute should still point to the mock, not the original method
        assert getattr(FakeAPIWithOriginal.create, "_original") is not FakeAPIWithOriginal.create
        # The original method should remain unchanged
        assert FakeAPIWithOriginal.create is original_api_with_original

        # Call the function to recover the APIs
        recover_openai_api()

        # Check that the _original attribute was removed for the method that didn't have it
        assert not hasattr(FakeAPIWithoutOriginal.create, "_original")
        assert not hasattr(FakeAPIWithOriginal.create, "_original")

        # The original methods should be restored
        assert FakeAPIWithoutOriginal.create is original_api_without_original
        assert FakeAPIWithOriginal.create is dummy_api
