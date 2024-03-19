from enum import Enum

import pytest
from unittest.mock import patch

from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._trace import TokenCollector, enrich_span_with_context, enrich_span_with_trace


class MockSpan:
    def __init__(self, span_context, parent=None, raise_exception_for_attr=False):
        self.span_context = span_context
        self.parent = parent
        self.raise_exception_for_attr = raise_exception_for_attr
        self.attributes = {}

    def get_span_context(self):
        return self.span_context

    def set_attribute(self, key, value):
        if not self.raise_exception_for_attr:
            self.attributes[key] = value
        else:
            raise Exception("Dummy Error")

    def set_attributes(self, attributes):
        if not self.raise_exception_for_attr:
            self.attributes.update(attributes)
        else:
            raise Exception("Dummy Error")


class MockSpanContext:
    def __init__(self, span_id):
        self.span_id = span_id


class MockOutput:
    def __init__(self, prompt_tokens, completion_token, total_tokens):
        self.usage = MockUsage(prompt_tokens, completion_token, total_tokens)


class MockUsage:
    def __init__(self, prompt_tokens, completion_token, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_token = completion_token
        self.total_tokens = total_tokens

    def dict(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_token": self.completion_token,
            "total_tokens": self.total_tokens
        }


class MockTrace:
    def __init__(self, name, type):
        self.name = name
        self.type = type


class MockTraceType(Enum):
    TYPE_1 = "type_1"


@pytest.mark.unittest
def test_token_collector():
    """
          1
        / |
        2  3
        |
        4
    """
    token_collector = TokenCollector()
    span_1 = MockSpan(MockSpanContext(1))
    span_2 = MockSpan(MockSpanContext(2), parent=span_1.span_context)
    span_3 = MockSpan(MockSpanContext(3), parent=span_1.span_context)
    span_4 = MockSpan(MockSpanContext(4), parent=span_2.span_context)

    output_3 = MockOutput(7, 13, 20)
    output_4 = MockOutput(17, 13, 30)
    token_collector.collect_openai_tokens(span_3, output_3)
    token_collector.collect_openai_tokens_for_parent_span(span_3)
    token_collector.collect_openai_tokens(span_4, output_4)
    token_collector.collect_openai_tokens_for_parent_span(span_4)
    token_collector.collect_openai_tokens_for_parent_span(span_2)
    token_collector.collect_openai_tokens_for_parent_span(span_1)
    assert token_collector._span_id_to_tokens == {
        1: {"prompt_tokens": 24, "completion_token": 26, "total_tokens": 50},
        2: {"prompt_tokens": 17, "completion_token": 13, "total_tokens": 30},
        3: {"prompt_tokens": 7, "completion_token": 13, "total_tokens": 20},
        4: {"prompt_tokens": 17, "completion_token": 13, "total_tokens": 30},
    }


@pytest.mark.unittest
def test_enrich_span_with_context(caplog):
    with patch.object(OperationContext, "_get_otel_attributes", return_value={"test_key": "test_value"}):
        # Normal case
        span = MockSpan(MockSpanContext(1))
        enrich_span_with_context(span)
        assert span.attributes == {"test_key": "test_value"}

        # Raise exception when update attributes
        span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
        enrich_span_with_context(span)
        assert caplog.records[0].levelname == "WARNING"
        assert "Failed to enrich span with context" in caplog.text


@pytest.mark.unittest
def test_enrich_span_with_trace(caplog):
    with patch("promptflow.tracing._trace.get_node_name_from_context", return_value="test_node_name"):
        # Normal case
        span = MockSpan(MockSpanContext(1))
        trace = MockTrace("test_trace", MockTraceType.TYPE_1)
        enrich_span_with_trace(span, trace)
        assert span.attributes == {
            "framework": "promptflow",
            "span_type": "type_1",
            "function": "test_trace",
            "node_name": "test_node_name"
        }

        # Raise exception when update attributes
        span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
        enrich_span_with_trace(span, trace)
        assert caplog.records[0].levelname == "WARNING"
        assert "Failed to enrich span with trace" in caplog.text


@pytest.mark.unittest
def test_traced_generator():
    pass

