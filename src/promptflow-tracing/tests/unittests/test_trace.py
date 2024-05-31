import asyncio
import json
import time
from enum import Enum
from unittest.mock import MagicMock, Mock, create_autospec, patch

import opentelemetry
import pytest
from openai.types.create_embedding_response import CreateEmbeddingResponse, Embedding, Usage
from opentelemetry.trace import Span, SpanKind
from opentelemetry.trace.status import StatusCode

from promptflow.tracing import _trace
from promptflow.tracing._experimental import enrich_prompt_template
from promptflow.tracing._operation_context import OperationContext
from promptflow.tracing._trace import (
    TokenCollector,
    _record_cancellation_exceptions_to_span,
    enrich_span_with_context,
    enrich_span_with_embedding,
    enrich_span_with_input,
    enrich_span_with_llm,
    enrich_span_with_openai_tokens,
    enrich_span_with_prompt_info,
    enrich_span_with_trace,
    handle_span_exception,
    serialize_attribute,
    start_as_current_span,
)
from promptflow.tracing.contracts.trace import TraceType


class MockSpan:
    def __init__(self, span_context, parent=None, raise_exception_for_attr=False):
        self.span_context = span_context
        self.name = "mock_span"
        self.parent = parent
        self.raise_exception_for_attr = raise_exception_for_attr
        self.attributes = {}
        self.events = []
        self.status = None
        self.description = None
        self.exception = None

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

    def add_event(self, name: str, attributes=None, timestamp=None):
        self.events.append(MockEvent(name, attributes, timestamp))

    def set_status(self, status=None, description=None):
        self.status = status
        self.description = description

    def record_exception(self, exception):
        self.exception = exception

    def is_recording(self):
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class MockEvent:
    def __init__(self, name, attributes, timestamp=None):
        self.name = name
        self.attributes = attributes
        self.timestamp = timestamp or int(time.time())


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
            "total_tokens": self.total_tokens,
        }


class MockTrace:
    def __init__(self, function, type):
        self.function = function
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
            "node_name": "test_node_name",
        }

        # Raise exception when update attributes
        span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
        enrich_span_with_trace(span, trace)
        assert caplog.records[0].levelname == "WARNING"
        assert "Failed to enrich span with trace" in caplog.text


@pytest.mark.unittest
def test_enrich_span_with_prompt_info(caplog):
    with patch("promptflow.tracing._trace.get_prompt_param_name_from_func", return_value="prompt_tpl"), patch(
        "promptflow.tracing._trace.get_input_names_for_prompt_template", return_value=["input_1", "input_2"]
    ):
        test_prompt_args = {"prompt_tpl": "prompt_tpl", "input_1": "value_1", "input_2": "value_2"}
        expected_prompt_info = {
            "prompt.template": "prompt_tpl",
            "prompt.variables": '{\n  "input_1": "value_1",\n  "input_2": "value_2"\n}',
        }

        # Normal case
        span = MockSpan(MockSpanContext(1))
        enrich_span_with_prompt_info(span, None, test_prompt_args)

        assert span.attributes == expected_prompt_info
        assert span.events[0].name == "promptflow.prompt.template"
        assert span.events[0].attributes == {"payload": serialize_attribute(expected_prompt_info)}

        # Raise exception when update attributes
        span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
        enrich_span_with_prompt_info(span, None, test_prompt_args)

        assert caplog.records[0].levelname == "WARNING"
        assert "Failed to enrich span with prompt info" in caplog.text


@pytest.mark.unittest
def test_enrich_span_with_input(caplog):
    # Normal case
    span = MockSpan(MockSpanContext(1))
    enrich_span_with_input(span, "input")
    assert span.attributes == {"inputs": '"input"'}

    # Raise exception when update attributes
    span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
    enrich_span_with_input(span, "input")
    assert caplog.records[0].levelname == "WARNING"
    assert "Failed to enrich span with input" in caplog.text


@pytest.mark.unittest
def test_enrich_span_with_openai_tokens(caplog):
    tokens = {"prompt_tokens": 10, "completion_token": 20, "total_tokens": 30}
    cumulative_tokens = {f"__computed__.cumulative_token_count.{k.split('_')[0]}": v for k, v in tokens.items()}
    llm_tokens = {f"llm.usage.{k}": v for k, v in tokens.items()}
    llm_tokens.update(cumulative_tokens)
    with patch("promptflow.tracing._trace.token_collector.try_get_openai_tokens", return_value=tokens):
        # Normal case
        span = MockSpan(MockSpanContext(1))
        enrich_span_with_openai_tokens(span, TraceType.FUNCTION)
        assert span.attributes == cumulative_tokens

        # LLM case
        span = MockSpan(MockSpanContext(1))
        enrich_span_with_openai_tokens(span, TraceType.LLM)
        assert span.attributes == llm_tokens

        # Embedding case
        span = MockSpan(MockSpanContext(1))
        enrich_span_with_openai_tokens(span, TraceType.EMBEDDING)
        assert span.attributes == llm_tokens

        # Raise exception when update attributes
        span = MockSpan(MockSpanContext(1), raise_exception_for_attr=True)
        enrich_span_with_openai_tokens(span, TraceType.FUNCTION)
        assert caplog.records[0].levelname == "WARNING"
        assert "Failed to enrich span with openai tokens" in caplog.text


@pytest.mark.unittest
def test_enrich_span_with_llm():
    span = MockSpan(MockSpanContext(1))
    model = "test_model"
    generated_message = "test_message"

    enrich_span_with_llm(span, model, generated_message)

    span.attributes == {
        "llm.response.model": model,
        "llm.generated_message": generated_message,
    }
    span.events[0].name == "promptflow.llm.generated_message"
    span.events[0].attributes == {"payload": serialize_attribute(generated_message)}


@pytest.mark.unittest
def test_enrich_span_with_embedding():
    span = MockSpan(MockSpanContext(1))
    test_inputs = {"input": "test"}
    test_embedding = Embedding(index=0, embedding=[0.1, 0.2, 0.3], object="embedding")
    usage = Usage(prompt_tokens=10, total_tokens=20)
    test_response = CreateEmbeddingResponse(model="gpt-3", data=[test_embedding], object="list", usage=usage)

    expected_embedding = [{"embedding.vector": "<3 dimensional vector>", "embedding.text": "test"}]
    expected_attributes = {
        "llm.response.model": "gpt-3",
        "embedding.embeddings": serialize_attribute(expected_embedding),
    }

    enrich_span_with_embedding(span, test_inputs, test_response)

    assert span.attributes == expected_attributes
    assert span.events[0].name == "promptflow.embedding.embeddings"
    assert span.events[0].attributes == {"payload": serialize_attribute(expected_embedding)}


@pytest.mark.unittest
def test_serialize_attribute_with_serializable_data():
    data = {"key": "value"}
    result = serialize_attribute(data)
    assert result == json.dumps(data, indent=2)


@pytest.mark.unittest
def test_serialize_attribute_with_non_serializable_data():
    class NonSerializable:
        pass

    data = NonSerializable()
    assert serialize_attribute(data) == json.dumps(str(data))


@pytest.mark.unittest
def test_set_enrich_prompt_template():
    mock_span = MockSpan(MockSpanContext(1))
    with patch.object(opentelemetry.trace, "get_current_span", return_value=mock_span):
        template = "mock prompt template"
        variables = {"key": "value"}
        enrich_prompt_template(template=template, variables=variables)

        assert template == mock_span.attributes["prompt.template"]
        assert variables == json.loads(mock_span.attributes["prompt.variables"])


@pytest.mark.unitests
def test_record_cancellation():
    mock_span = MockSpan(MockSpanContext(1))
    try:
        with _record_cancellation_exceptions_to_span(mock_span):
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    assert mock_span.status == StatusCode.ERROR
    assert "Execution cancelled" in mock_span.description
    assert isinstance(mock_span.exception, KeyboardInterrupt)

    mock_span = MockSpan(MockSpanContext(1))
    try:
        with _record_cancellation_exceptions_to_span(mock_span):
            raise asyncio.CancelledError
    except asyncio.CancelledError:
        pass
    assert mock_span.status == StatusCode.ERROR
    assert "Execution cancelled" in mock_span.description
    assert isinstance(mock_span.exception, asyncio.CancelledError)


@pytest.mark.unittest
def test_start_as_current_span_starts_and_ends_span():
    tracer = Mock()
    mock_span = MagicMock()
    tracer.start_as_current_span.return_value = mock_span

    with start_as_current_span(tracer, "test_span") as span:
        pass

    tracer.start_as_current_span.assert_called_once_with(
        "test_span", None, SpanKind.INTERNAL, None, (), None, True, True, end_on_exit=False
    )
    span.end.assert_called_once()


@pytest.mark.unittest
def test_start_as_current_span_does_not_end_when_should_end_is_false():
    tracer = Mock()
    mock_span = MagicMock()
    tracer.start_as_current_span.return_value = mock_span

    with start_as_current_span(tracer, "test_span") as span:
        setattr(span, "__should_end", False)
        pass

    span.end.assert_not_called()


@pytest.mark.unittest
def test_start_as_current_span_throws_exception_on_enter():
    tracer = Mock()
    mock_span = MagicMock()
    mock_span.__enter__.side_effect = Exception("Test Exception")
    tracer.start_as_current_span.return_value = mock_span

    with pytest.raises(Exception) as e:
        with start_as_current_span(tracer, "test_span"):
            pass

    assert str(e.value) == "Test Exception"


@pytest.mark.unittest
def test_start_as_current_span_handles_exception():
    tracer = Mock()
    tracer.start_as_current_span.return_value = MagicMock()
    exception = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        with patch.object(_trace, "handle_span_exception") as mock_handle_span_exception:
            with start_as_current_span(tracer, "test_span") as span:
                raise exception

    mock_handle_span_exception.assert_called_once_with(span, exception)
    span.end.assert_called_once()


@pytest.mark.unittest
def test_handle_span_exception():
    span = create_autospec(Span)

    span.is_recording.return_value = True
    exception = Exception("test exception")

    handle_span_exception(span, exception)

    assert span.record_exception.called
    called_status = span.set_status.call_args[0][0]
    assert called_status.status_code == StatusCode.ERROR
    assert called_status.description == "Exception: test exception"
