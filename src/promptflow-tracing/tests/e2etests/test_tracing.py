import asyncio
import json
import uuid
from unittest.mock import patch

import openai
import pytest
from opentelemetry.trace.status import StatusCode

from promptflow.tracing._integrations._openai_injector import inject_openai_api
from promptflow.tracing._trace import TracedIterator
from promptflow.tracing.contracts.trace import TraceType

from ..utils import execute_function_in_subprocess, prepare_memory_exporter
from .simple_functions import (
    dummy_llm_tasks_async,
    dummy_llm_tasks_threadpool,
    greetings,
    openai_chat,
    openai_chat_async,
    openai_completion,
    openai_completion_async,
    openai_embedding_async,
    prompt_tpl_chat,
    prompt_tpl_completion,
)

LLM_FUNCTION_NAMES = [
    "openai.resources.chat.completions.Completions.create",
    "openai.resources.completions.Completions.create",
    "openai.resources.chat.completions.AsyncCompletions.create",
    "openai.resources.completions.AsyncCompletions.create",
]

EMBEDDING_FUNCTION_NAMES = [
    "openai.resources.embeddings.Embeddings.create",
    "openai.resources.embeddings.AsyncEmbeddings.create",
]

LLM_TOKEN_NAMES = [
    "llm.usage.prompt_tokens",
    "llm.usage.completion_tokens",
    "llm.usage.total_tokens",
    "llm.response.model",
]

EMBEDDING_TOKEN_NAMES = [
    "llm.usage.prompt_tokens",
    "llm.usage.total_tokens",
    "llm.response.model",
]

CUMULATIVE_LLM_TOKEN_NAMES = [
    "__computed__.cumulative_token_count.prompt",
    "__computed__.cumulative_token_count.completion",
    "__computed__.cumulative_token_count.total",
]

CUMULATIVE_EMBEDDING_TOKEN_NAMES = [
    "__computed__.cumulative_token_count.prompt",
    "__computed__.cumulative_token_count.total",
]

SPAN_TYPE_ATTRIBUTE = "span_type"
FRAMEWORK_ATTRIBUTE = "framework"
FUNCTION_ATTRIBUTE = "function"
EXPECTED_FRAMEWORK = "promptflow"

ITERATED_SPAN_PREFIX = "Iterated("
EMBEDDING_VECTOR = "embedding.vector"
EMBEDDING_TEXT = "embedding.text"
INPUT = "input"
DIMENSIONAL_TOKEN = "dimensional token"
PROMPT_TEMPLATE = "prompt.template"
PROMPT_VARIABLES = "prompt.variables"

FUNCTION_INPUTS_EVENT = "promptflow.function.inputs"
FUNCTION_OUTPUT_EVENT = "promptflow.function.output"
EMBEDDING_EVENT = "promptflow.embedding.embeddings"
RETRIEVAL_QUERY_EVENT = "promptflow.retrieval.query"
RETRIEVAL_DOCUMENTS_EVENT = "promptflow.retrieval.documents"
PROMPT_TEMPLATE_EVENT = "promptflow.prompt.template"
LLM_GENERATED_MESSAGE_EVENT = "promptflow.llm.generated_message"
BUILTIN_EVENT_NAMES = {
    FUNCTION_INPUTS_EVENT,
    FUNCTION_OUTPUT_EVENT,
    EMBEDDING_EVENT,
    RETRIEVAL_QUERY_EVENT,
    RETRIEVAL_DOCUMENTS_EVENT,
    LLM_GENERATED_MESSAGE_EVENT,
    PROMPT_TEMPLATE_EVENT,
}


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestTracing:
    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (greetings, {"user_id": 1}, 4),
            (dummy_llm_tasks_async, {"prompt": "Hello", "models": ["model_1", "model_1"]}, 3),
            (dummy_llm_tasks_threadpool, {"prompt": "Hello", "models": ["model_1", "model_1"]}, 5),
        ],
    )
    def test_otel_trace(self, func, inputs, expected_span_length):
        execute_function_in_subprocess(self.assert_otel_trace, func, inputs, expected_span_length)

    def assert_otel_trace(self, func, inputs, expected_span_length):
        exporter = prepare_memory_exporter()

        result = self.run_func(func, inputs)
        assert isinstance(result, (str, list))
        span_list = exporter.get_finished_spans()
        self.validate_span_list(span_list, expected_span_length)

    @pytest.mark.skip(reason="pf-tracing is being replaced by AI foundry tracing features. Skipping these flaky tests.")
    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (prompt_tpl_completion, {"prompt_tpl": "Hello {{name}}", "name": "world"}, 2),
            (
                prompt_tpl_chat,
                {
                    "prompt_tpl": "system:\nYou are a helpful assistant.\n\n\nuser:\n{{question}}",
                    "question": "What is ChatGPT?",
                },
                2,
            ),
            (prompt_tpl_completion, {"prompt_tpl": "Hello {{name}}", "name": "world", "stream": True}, 2),
            (
                prompt_tpl_chat,
                {
                    "prompt_tpl": "system:\nYou are a helpful assistant.\n\n\nuser:\n{{question}}",
                    "question": "What is ChatGPT?",
                    "stream": True,
                },
                2,
            ),
        ],
    )
    def test_otel_traces_with_prompt(self, dev_connections, func, inputs, expected_span_length):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_prompt, dev_connections, func, inputs, expected_span_length
        )

    def assert_otel_traces_with_prompt(self, dev_connections, func, inputs, expected_span_length):
        memory_exporter = prepare_memory_exporter()

        inputs = self.add_azure_connection_to_inputs(inputs, dev_connections)
        is_stream = inputs.get("stream", False)
        with patch("promptflow.tracing._trace.get_prompt_param_name_from_func", return_value="prompt_tpl"):
            self.run_func(func, inputs)

            span_list = memory_exporter.get_finished_spans()
            assert (
                len(span_list) == expected_span_length
            ), f"Expected {expected_span_length} spans, but got {len(span_list)}."
            self.validate_span_list(span_list, expected_span_length)
            self.validate_openai_tokens(span_list, is_stream)

            # Extract the root span and validate the prompt template value is correctly set.
            root_span = next(span for span in span_list if span.parent is None)
            events = self.load_builtin_events(root_span)
            assert PROMPT_TEMPLATE_EVENT in events, f"Expected '{PROMPT_TEMPLATE_EVENT}' in events"
            assert events[PROMPT_TEMPLATE_EVENT][PROMPT_TEMPLATE] == inputs["prompt_tpl"], "Mismatch in prompt template"
            prompt_variables = json.loads(events[PROMPT_TEMPLATE_EVENT][PROMPT_VARIABLES])
            assert all(item in inputs.items() for item in prompt_variables.items()), "Mismatch in prompt variables"

    @pytest.mark.skip(reason="TODO: Fix this test in following PRs.")
    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (openai_chat, {"prompt": "Hello"}, 2),
            (openai_completion, {"prompt": "Hello"}, 2),
            (openai_chat, {"prompt": "Hello", "stream": True}, 2),
            (openai_completion, {"prompt": "Hello", "stream": True}, 2),
            (openai_chat_async, {"prompt": "Hello"}, 2),
            (openai_completion_async, {"prompt": "Hello"}, 2),
            (openai_chat_async, {"prompt": "Hello", "stream": True}, 2),
            (openai_completion_async, {"prompt": "Hello", "stream": True}, 2),
        ],
    )
    def test_otel_trace_with_llm(self, dev_connections, func, inputs, expected_span_length):
        execute_function_in_subprocess(
            self.assert_otel_trace_with_llm, dev_connections, func, inputs, expected_span_length
        )

    def test_open_ai_stream_context_manager(self, dev_connections):
        inject_openai_api()
        conn_name = "azure_open_ai_connection"
        conn_dict = {
            "api_key": dev_connections[conn_name]["value"]["api_key"],
            "azure_endpoint": dev_connections[conn_name]["value"]["api_base"],
            "api_version": dev_connections[conn_name]["value"]["api_version"],
        }
        client = openai.AzureOpenAI(**conn_dict)

        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello"}]
        response = client.chat.completions.create(model="gpt-35-turbo", messages=messages, stream=True)
        assert isinstance(response, TracedIterator)
        assert isinstance(response._iterator, openai.Stream)

        with patch.object(openai.Stream, "__enter__") as mock_enter, patch.object(
            openai.Stream, "__exit__"
        ) as mock_exit:

            def generator():
                with response:
                    mock_enter.assert_called_once()
                    mock_exit.enter.assert_not_called()
                    for chunk in response:
                        if chunk.choices:
                            yield chunk.choices[0].delta.content or ""

            _ = "".join(generator())
            mock_exit.assert_called_once()

    def assert_otel_trace_with_llm(self, dev_connections, func, inputs, expected_span_length):
        inject_openai_api()
        exporter = prepare_memory_exporter()

        inputs = self.add_azure_connection_to_inputs(inputs, dev_connections)
        is_stream = inputs.get("stream", False)
        result = self.run_func(func, inputs)
        assert isinstance(result, str)
        span_list = exporter.get_finished_spans()
        self.validate_span_list(span_list, expected_span_length)
        # We updated the OpenAI tokens (prompt_token/completion_token/total_token) to the span attributes
        # for llm and embedding traces, and aggregate them to the parent span. Use this function to validate
        # the openai tokens are correctly set.
        self.validate_openai_tokens(span_list, is_stream)

    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (openai_embedding_async, {"input": "Hello"}, 2),
            # [9906] is the tokenized version of "Hello"
            (openai_embedding_async, {"input": [9906]}, 2),
        ],
    )
    def test_otel_trace_with_embedding(
        self,
        dev_connections,
        func,
        inputs,
        expected_span_length,
    ):
        execute_function_in_subprocess(
            self.assert_otel_traces_with_embedding, dev_connections, func, inputs, expected_span_length
        )

    def assert_otel_traces_with_embedding(self, dev_connections, func, inputs, expected_span_length):
        inject_openai_api()
        memory_exporter = prepare_memory_exporter()

        inputs = self.add_azure_connection_to_inputs(inputs, dev_connections)
        result = self.run_func(func, inputs)
        assert isinstance(result, list)

        span_list = memory_exporter.get_finished_spans()
        self.validate_span_list(span_list, expected_span_length)
        self.validate_openai_tokens(span_list)

    def test_otel_trace_with_multiple_functions(self):
        execute_function_in_subprocess(self.assert_otel_traces_with_multiple_functions)

    def _assert_otel_tracer_collection_after_start_trace(self):
        from promptflow.tracing import start_trace

        memory_exporter = prepare_memory_exporter()
        inputs = {"user_id": 1}
        collection1 = str(uuid.uuid4())
        start_trace(collection=collection1)
        self.run_func(greetings, inputs)
        span_list = memory_exporter.get_finished_spans()
        assert len(span_list) > 0
        for span in span_list:
            assert span.resource.attributes["collection"] == collection1
        # resource.attributes.collection should be refreshed after start_trace
        collection2 = str(uuid.uuid4())
        start_trace(collection=collection2)
        self.run_func(greetings, inputs)
        new_span_list = memory_exporter.get_finished_spans()
        assert len(new_span_list) > len(span_list)
        for span in new_span_list[len(span_list) :]:
            assert span.resource.attributes["collection"] == collection2

    def test_otel_tracer_refreshed_after_start_trace(self):
        execute_function_in_subprocess(self._assert_otel_tracer_collection_after_start_trace)

    def assert_otel_traces_with_multiple_functions(self):
        memory_exporter = prepare_memory_exporter()

        result = self.run_func(greetings, {"user_id": 1})
        assert isinstance(result, str)
        result = self.run_func(dummy_llm_tasks_async, {"prompt": "Hello", "models": ["model_1", "model_1"]})
        assert isinstance(result, list)

        span_list = memory_exporter.get_finished_spans()
        assert len(span_list) == 7, f"Got {len(span_list)} spans."  # 4 + 3 spans in total
        root_spans = [span for span in span_list if span.parent is None]
        assert len(root_spans) == 2, f"Expected 2 root spans, got {len(root_spans)}"
        assert root_spans[0].attributes["function"] == "greetings"
        assert root_spans[1].attributes["function"] == "dummy_llm_tasks_async"
        assert root_spans[1] == span_list[-1]  # It should be the last span
        sub_level_span = span_list[-2]  # It should be the second last span
        expected_values = {
            "framework": "promptflow",
            "span_type": "Function",
        }
        for span in span_list:
            for k, v in expected_values.items():
                assert span.attributes[k] == v, f"span.attributes[{k}] = {span.attributes[k]}, expected: {v}"
        assert (
            sub_level_span.parent.span_id == root_spans[1].context.span_id
        )  # sub_level_span is a child of the second root span

    def run_func(self, func, inputs):
        if asyncio.iscoroutinefunction(func):
            return asyncio.run(func(**inputs))
        else:
            return func(**inputs)

    def add_azure_connection_to_inputs(self, inputs, dev_connections):
        conn_name = "azure_open_ai_connection"
        if conn_name not in dev_connections:
            raise ValueError(f"Connection '{conn_name}' not found in dev connections.")
        conn_dict = {
            "api_key": dev_connections[conn_name]["value"]["api_key"],
            "azure_endpoint": dev_connections[conn_name]["value"]["api_base"],
            "api_version": dev_connections[conn_name]["value"]["api_version"],
        }
        inputs["connection"] = conn_dict
        return inputs

    def validate_span_type(self, span):
        if span.attributes.get("function", "") in LLM_FUNCTION_NAMES:
            expected_span_type = TraceType.LLM
        elif span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
            expected_span_type = TraceType.EMBEDDING
        else:
            expected_span_type = TraceType.FUNCTION
        assert span.attributes["span_type"] == expected_span_type

    def validate_span_events(self, span):
        events = self.load_builtin_events(span)
        assert FUNCTION_INPUTS_EVENT in events, f"Expected '{FUNCTION_INPUTS_EVENT}' in events"
        assert FUNCTION_OUTPUT_EVENT in events, f"Expected '{FUNCTION_OUTPUT_EVENT}' in events"

        if span.attributes[SPAN_TYPE_ATTRIBUTE] == TraceType.LLM:
            self.validate_llm_event(events)
        elif span.attributes[SPAN_TYPE_ATTRIBUTE] == TraceType.EMBEDDING:
            self.validate_embedding_event(events)

        if PROMPT_TEMPLATE_EVENT in events:
            self.validate_prompt_template_event(events)

    def validate_llm_event(self, span_events):
        assert LLM_GENERATED_MESSAGE_EVENT in span_events, f"Expected '{LLM_GENERATED_MESSAGE_EVENT}' in span events"

    def validate_embedding_event(self, span_events):
        assert EMBEDDING_EVENT in span_events, f"Expected '{EMBEDDING_EVENT}' in span events"
        embeddings = json.dumps(span_events[EMBEDDING_EVENT])
        assert EMBEDDING_VECTOR in embeddings, f"Expected '{EMBEDDING_VECTOR}' in embeddings"
        assert EMBEDDING_TEXT in embeddings, f"Expected '{EMBEDDING_TEXT}' in embeddings"

        assert INPUT in span_events[FUNCTION_INPUTS_EVENT], f"Expected '{INPUT}' in function inputs"
        embeddings_input = span_events[FUNCTION_INPUTS_EVENT].get(INPUT)

        if isinstance(embeddings_input, list):
            # If the input is a token array, which is list of int, the attribute should contains
            # the length of the token array '<len(token_array) dimensional token>'.
            assert (
                DIMENSIONAL_TOKEN in embeddings
            ), f"Expected '{DIMENSIONAL_TOKEN}' in embeddings for token array input"
        else:
            # If the input is a string, the attribute should contains the original input string.
            assert embeddings_input in embeddings, f"Expected input string '{embeddings_input}' in embeddings"

    def validate_prompt_template_event(self, span_events):
        assert PROMPT_TEMPLATE_EVENT in span_events, f"Expected '{PROMPT_TEMPLATE_EVENT}' in span events"
        assert (
            PROMPT_TEMPLATE in span_events[PROMPT_TEMPLATE_EVENT]
        ), f"Expected '{PROMPT_TEMPLATE}' in {PROMPT_TEMPLATE_EVENT}"
        assert (
            PROMPT_VARIABLES in span_events[PROMPT_TEMPLATE_EVENT]
        ), f"Expected '{PROMPT_VARIABLES}' in {PROMPT_TEMPLATE_EVENT}"

    def validate_span_list(self, span_list, expected_span_length):
        assert (
            len(span_list) == expected_span_length
        ), f"Expected {expected_span_length} spans, but got {len(span_list)}."
        root_spans = [span for span in span_list if span.parent is None]
        names = ",".join([span.name for span in span_list])
        msg = f"Expected exactly one root span but got {len(root_spans)}: {names}."
        assert len(root_spans) == 1, msg
        root_span = root_spans[0]
        for span in span_list:
            assert span.status.status_code == StatusCode.OK, "Expected status code to be OK."
            assert isinstance(span.name, str), "Expected span name to be a string."
            assert (
                span.attributes[FRAMEWORK_ATTRIBUTE] == EXPECTED_FRAMEWORK
            ), f"Expected framework attribute to be '{EXPECTED_FRAMEWORK}'."
            if span != root_span:  # Non-root spans should have a parent
                assert FUNCTION_ATTRIBUTE in span.attributes, "Expected non-root spans to have a function attribute."

            self.validate_span_type(span)
            self.validate_span_events(span)

    def load_builtin_events(self, span):
        events_dict = {}
        for event in span.events:
            if event.name in events_dict:
                raise ValueError(f"Duplicate event {event.name} found in span {span.name}")
            if event.name in BUILTIN_EVENT_NAMES:
                try:
                    payload = json.loads(event.attributes["payload"])
                    events_dict[event.name] = payload
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Failed to parse payload for event {event.name}. Payload: {event.attributes['payload']}"
                    )
        return events_dict

    def validate_openai_tokens(self, span_list, is_stream=False):
        span_dict = {span.context.span_id: span for span in span_list}
        expected_tokens = {}
        for span in span_list:
            tokens = None
            # Validate the openai tokens are correctly set in the llm trace.
            if self._is_llm_span_with_tokens(span, is_stream):
                for token_name in LLM_TOKEN_NAMES + CUMULATIVE_LLM_TOKEN_NAMES:
                    assert token_name in span.attributes
                tokens = {token_name: span.attributes[token_name] for token_name in CUMULATIVE_LLM_TOKEN_NAMES}
            # Validate the openai tokens are correctly set in the embedding trace.
            if span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                for token_name in EMBEDDING_TOKEN_NAMES + CUMULATIVE_EMBEDDING_TOKEN_NAMES:
                    assert token_name in span.attributes
                tokens = {token_name: span.attributes[token_name] for token_name in CUMULATIVE_EMBEDDING_TOKEN_NAMES}
            # Aggregate the tokens to the parent span.
            if tokens is not None:
                current_span_id = span.context.span_id
                while True:
                    if current_span_id in expected_tokens:
                        expected_tokens[current_span_id] = {
                            key: expected_tokens[current_span_id][key] + tokens[key] for key in tokens
                        }
                    else:
                        expected_tokens[current_span_id] = tokens
                    parent_cxt = getattr(span_dict[current_span_id], "parent", None)
                    if parent_cxt is None:
                        break
                    current_span_id = parent_cxt.span_id
        # Validate the aggregated tokens are correctly set in the parent span.
        for span in span_list:
            span_id = span.context.span_id
            if span_id in expected_tokens:
                for token_name in expected_tokens[span_id]:
                    assert span.attributes[token_name] == expected_tokens[span_id][token_name]

    def _is_llm_span_with_tokens(self, span, is_stream):
        """
        This function checks if a given span is a LLM span with tokens.

        If in stream mode, the function checks if the span has attributes indicating it's an iterated span.
        In non-stream mode, it simply checks if the span's function attribute is in the list of LLM function names.

        Args:
            span: The span to check.
            is_stream: A boolean indicating whether the span is in stream mode.

        Returns:
            A boolean indicating whether the span is a LLM span with tokens.
        """
        if is_stream:
            return (
                span.attributes.get("function", "") in LLM_FUNCTION_NAMES
                and span.attributes.get("output_type", "") == "iterated"
            )
        else:
            return span.attributes.get("function", "") in LLM_FUNCTION_NAMES
