import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import format_span_id, format_trace_id, get_current_span, get_tracer, set_tracer_provider

from promptflow.tracing import trace
from promptflow.tracing._experimental import EvaluationContext


def prepare_memory_exporter():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    set_tracer_provider(provider)
    return exporter


@trace
def do_nothing():
    pass


@trace
def assert_eval_span(last: ReadableSpan):
    current_span = get_current_span()
    assert isinstance(current_span, ReadableSpan)
    attrs = current_span.attributes
    last_ctx = last.get_span_context()
    trace_id = f"0x{format_trace_id(last_ctx.trace_id)}"
    span_id = f"0x{format_span_id(last_ctx.span_id)}"
    for key, value in [
        ("referenced.trace_id", trace_id),
        ("referenced.span_id", span_id),
        # For the span without line_run_id, it should use trace_id as line_run_id
        ("referenced.line_run_id", trace_id),
    ]:
        value_in_attrs = attrs.get(key)
        assert value_in_attrs == value, f"Expect {value} but got {value_in_attrs} for key {key}"


@pytest.mark.unittest
def test_evaluation_context():
    prepare_memory_exporter()
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("test_span") as span:
        last = span
        # Currently only when traced function is called in the same thread
        # the context can be correctly set
        # TODO: Even the user doesn't use @trace, we should still be able to set the context
        do_nothing()
    with EvaluationContext():
        assert_eval_span(last)
