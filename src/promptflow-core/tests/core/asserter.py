import json
from typing import List

from opentelemetry.trace.status import StatusCode

from promptflow.contracts.run_info import Status
from promptflow.executor._result import LineResult
from promptflow.tracing.contracts.trace import TraceType


def run_assertions(asserter, configs):
    for item in configs:
        assert_func = getattr(asserter, f"assert_{item['type']}", None)
        if assert_func is None:
            raise ValueError(f"Unsupported assertion type: {item['type']}")
        assert_kwargs = item.get("expections", None)
        if assert_kwargs is not None:
            assert_func(**assert_kwargs)
        else:
            assert_func()


class LineResultAsserter:
    def __init__(self, line_result: LineResult, node_count: int):
        self.line_result = line_result
        self.node_count = node_count

    def assert_output(self, expected_output):
        assert self.line_result.output == expected_output

    def assert_run_info(self):
        assert self.line_result.run_info.status == Status.Completed
        assert isinstance(self.line_result.run_info.api_calls, list)
        assert len(self.line_result.run_info.api_calls) == 1
        assert (
            isinstance(self.line_result.run_info.api_calls[0]["children"], list)
            and len(self.line_result.run_info.api_calls[0]["children"]) == self.node_count
        )
        assert len(self.line_result.node_run_infos) == self.node_count
        for node, node_run_info in self.line_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert node_run_info.node == node
            assert isinstance(node_run_info.api_calls, list)


class RunTrackerAsserter:
    def __init__(self, run_tracker):
        self.run_tracker = run_tracker

    def assert_run(self):
        assert not self.run_tracker._flow_runs, "Flow runs in run tracker should be empty."
        assert not self.run_tracker._node_runs, "Node runs in run tracker should be empty."


class OtelTraceAsserter:
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

    def __init__(self, span_list: List, run_id: str, is_batch: bool = False, is_stream: bool = False):
        self.span_list = span_list
        self.run_id = run_id
        self.is_batch = is_batch
        self.is_stream = is_stream

    def assert_basic(self, expected_span_length, expected_root_span_count):
        assert len(self.span_list) == expected_span_length, f"Got {len(self.span_list)} spans."
        root_spans = [span for span in self.span_list if span.parent is None]
        assert len(root_spans) == expected_root_span_count, f"Got {len(root_spans)} root spans."
        for span in self.span_list:
            assert span.status.status_code == StatusCode.OK
            assert isinstance(span.name, str)
            for span in self.span_list:
                if self.is_batch:
                    assert span.attributes["batch_run_id"] == self.run_id
                else:
                    assert span.attributes["line_run_id"] == self.run_id
            assert span.attributes["framework"] == "promptflow"
            if span.parent is None:
                expected_span_type = TraceType.FLOW
            elif span.attributes.get("function", "") in OtelTraceAsserter.LLM_FUNCTION_NAMES:
                expected_span_type = TraceType.LLM
            elif span.attributes.get("function", "") in OtelTraceAsserter.EMBEDDING_FUNCTION_NAMES:
                expected_span_type = TraceType.EMBEDDING
            else:
                expected_span_type = TraceType.FUNCTION
            msg = f"span_type: {span.attributes['span_type']}, expected: {expected_span_type}"
            assert span.attributes["span_type"] == expected_span_type, msg
            if span not in root_spans:  # Non-root spans should have a parent
                assert span.attributes["function"]
            inputs = json.loads(span.attributes["inputs"])
            output = json.loads(span.attributes["output"])
            assert isinstance(inputs, dict)
            assert output is not None

    def assert_openai_tokens(self):
        span_dict = {span.context.span_id: span for span in self.span_list}
        expected_tokens = {}
        for span in self.span_list:
            tokens = None
            # Validate the openai tokens are correctly set in the llm trace.
            if self._is_llm_span_with_tokens(span):
                expected_token_names = OtelTraceAsserter.LLM_TOKEN_NAMES + OtelTraceAsserter.CUMULATIVE_LLM_TOKEN_NAMES
                for token_name in expected_token_names:
                    assert token_name in span.attributes
                tokens = {
                    token_name: span.attributes[token_name]
                    for token_name in OtelTraceAsserter.CUMULATIVE_LLM_TOKEN_NAMES
                }
            # Validate the openai tokens are correctly set in the embedding trace.
            if span.attributes.get("function", "") in OtelTraceAsserter.EMBEDDING_FUNCTION_NAMES:
                expected_token_names = (
                    OtelTraceAsserter.EMBEDDING_TOKEN_NAMES + OtelTraceAsserter.CUMULATIVE_EMBEDDING_TOKEN_NAMES
                )
                for token_name in expected_token_names:
                    assert token_name in span.attributes
                tokens = {
                    token_name: span.attributes[token_name]
                    for token_name in OtelTraceAsserter.CUMULATIVE_EMBEDDING_TOKEN_NAMES
                }
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
        for span in self.span_list:
            span_id = span.context.span_id
            if span_id in expected_tokens:
                for token_name in expected_tokens[span_id]:
                    assert span.attributes[token_name] == expected_tokens[span_id][token_name]

    def _is_llm_span_with_tokens(self, span):
        # For streaming mode, there are two spans for openai api call, one is the original span, and the other
        # is the iterated span, which name is "Iterated(<original_trace_name>)", we should check the iterated span
        # in streaming mode.
        if self.is_stream:
            return span.attributes.get("function", "") in OtelTraceAsserter.LLM_FUNCTION_NAMES and span.name.startswith(
                "Iterated("
            )
        else:
            return span.attributes.get("function", "") in OtelTraceAsserter.LLM_FUNCTION_NAMES
