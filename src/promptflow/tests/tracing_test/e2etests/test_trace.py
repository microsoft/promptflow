import asyncio
import json

import pytest
from opentelemetry.trace.status import StatusCode

from promptflow.tracing._openai_injector import inject_openai_api
from promptflow.tracing.contracts.trace import TraceType

from ..utils import execute_function_in_subprocess, prepare_memory_exporter
from .simple_functions import (
    dummy_llm_tasks_async,
    greetings,
    openai_chat,
    openai_completion,
    openai_embedding_async,
    render_prompt_template,
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


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestTracing:
    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (greetings, {"user_id": 1}, 4),
            (dummy_llm_tasks_async, {"prompt": "Hello", "models": ["model_1", "model_1"]}, 3),
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

    @pytest.mark.parametrize(
        "func, inputs",
        [
            (render_prompt_template, {"prompt": "Hello {{name}}!", "name": "world"}),
        ],
    )
    def test_otel_trace_with_prompt(self, func, inputs):
        execute_function_in_subprocess(self.assert_otel_traces_with_prompt, func, inputs)

    def assert_otel_traces_with_prompt(self, func, inputs):
        memory_exporter = prepare_memory_exporter()

        result = self.run_func(func, inputs)
        assert result == "Hello world!"

        span_list = memory_exporter.get_finished_spans()
        for span in span_list:
            assert span.status.status_code == StatusCode.OK
            assert isinstance(span.name, str)
            if span.attributes.get("function", "") == "render_prompt_template":
                assert "prompt.template" in span.attributes
                assert span.attributes["prompt.template"] == inputs["prompt"]
                assert "prompt.variables" in span.attributes
                for var in inputs:
                    if var == "prompt":
                        continue
                    assert var in span.attributes["prompt.variables"]

    @pytest.mark.parametrize(
        "func, inputs, expected_span_length",
        [
            (openai_chat, {"prompt": "Hello"}, 2),
            (openai_completion, {"prompt": "Hello"}, 2),
            (openai_chat, {"prompt": "Hello", "stream": True}, 3),
            (openai_completion, {"prompt": "Hello", "stream": True}, 3),
        ],
    )
    def test_otel_trace_with_llm(self, dev_connections, func, inputs, expected_span_length):
        execute_function_in_subprocess(
            self.assert_otel_trace_with_llm, dev_connections, func, inputs, expected_span_length
        )

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
        for span in span_list:
            if self._is_llm_span_with_tokens(span, is_stream):
                assert span.attributes.get("llm.response.model", "") in ["gpt-35-turbo", "text-ada-001"]

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
        for span in span_list:
            if span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                assert span.attributes.get("llm.response.model", "") == "ada"
                embeddings = span.attributes.get("embedding.embeddings", "")
                assert "embedding.vector" in embeddings
                assert "embedding.text" in embeddings
                if isinstance(inputs["input"], list):
                    # If the input is a token array, which is list of int, the attribute should contains
                    # the length of the token array '<len(token_array) dimensional token>'.
                    assert "dimensional token" in embeddings
                else:
                    # If the input is a string, the attribute should contains the original input string.
                    assert inputs["input"] in embeddings

    def test_otel_trace_with_multiple_functions(self):
        execute_function_in_subprocess(self.assert_otel_traces_with_multiple_functions)

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

    def validate_span_list(self, span_list, expected_span_length):
        assert len(span_list) == expected_span_length, f"Got {len(span_list)} spans."
        root_spans = [span for span in span_list if span.parent is None]
        assert len(root_spans) == 1
        root_span = root_spans[0]
        for span in span_list:
            assert span.status.status_code == StatusCode.OK
            assert isinstance(span.name, str)
            assert span.attributes["framework"] == "promptflow"
            if span.attributes.get("function", "") in LLM_FUNCTION_NAMES:
                expected_span_type = TraceType.LLM
            elif span.attributes.get("function", "") in EMBEDDING_FUNCTION_NAMES:
                expected_span_type = TraceType.EMBEDDING
            else:
                expected_span_type = TraceType.FUNCTION
            msg = f"span_type: {span.attributes['span_type']}, expected: {expected_span_type}"
            assert span.attributes["span_type"] == expected_span_type, msg
            if span != root_span:  # Non-root spans should have a parent
                assert span.attributes["function"]
            inputs = json.loads(span.attributes["inputs"])
            output = json.loads(span.attributes["output"])
            assert isinstance(inputs, dict)
            assert output is not None

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
        # For streaming mode, there are two spans for openai api call, one is the original span, and the other
        # is the iterated span, which name is "Iterated(<original_trace_name>)", we should check the iterated span
        # in streaming mode.
        if is_stream:
            return span.attributes.get("function", "") in LLM_FUNCTION_NAMES and span.name.startswith("Iterated(")
        else:
            return span.attributes.get("function", "") in LLM_FUNCTION_NAMES
