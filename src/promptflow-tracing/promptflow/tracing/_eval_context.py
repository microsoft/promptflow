import contextlib
from typing import Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import format_span_id, format_trace_id

from ._operation_context import OperationContext
from ._trace import get_last_span


@contextlib.contextmanager
def evaluation_context(span: Optional[ReadableSpan] = None):
    if span is None:
        span = get_last_span()
    if not isinstance(span, ReadableSpan):
        yield
        return
    trace_id = f"0x{format_trace_id(span.context.trace_id)}"
    line_run_id = span.attributes.get("line_run_id") or trace_id
    ctx = OperationContext.get_instance()
    ctx._add_otel_attributes("referenced.line_run_id", line_run_id)
    try:
        yield
    finally:
        ctx._remove_otel_attributes(["referenced.line_run_id"])


class EvaluationContext:
    def __init__(self, span: Optional[ReadableSpan] = None):
        self._span_to_evaluate = span
        self._otel_attributes = {}
        if span is None:
            span = get_last_span()
        if span is None:
            return
        trace_id = f"0x{format_trace_id(span.context.trace_id)}"
        self._otel_attributes = {
            "referenced.line_run_id": span.attributes.get("line_run_id") or trace_id,
            "referenced.trace_id": trace_id,
            "referenced.span_id": f"0x{format_span_id(span.context.span_id)}",
        }
        self._original_attributes = {}
        self._original_ctx = OperationContext.get_instance()

    def __enter__(self):
        #  Add the OTel attributes to the current context
        self._original_ctx = OperationContext.get_instance()
        self._original_attributes = self._original_ctx._get_otel_attributes().copy()
        for key, value in self._otel_attributes.items():
            self._original_ctx._add_otel_attributes(key, value)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        #  Restore the original context
        self._original_ctx._remove_otel_attributes(list(self._otel_attributes.keys()))
        for key, value in self._original_attributes.items():
            self._original_ctx._add_otel_attributes(key, value)
        return False  # Propagate exceptions, if any
