import json
import os
from typing import Sequence

from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ReadableSpan,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import ProxyTracerProvider, get_tracer, get_tracer_provider


class MemoryExporter(SpanExporter):
    """Implementation of :class:`SpanExporter` that prints spans to the
    console.

    This class can be used for diagnostic purposes. It prints the exported
    spans to the console STDOUT.
    """

    def __init__(self):
        self._spans = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        print("exporting", spans)
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def spans(self) -> Sequence[ReadableSpan]:
        return [json.loads(span.to_json()) for span in self._spans]


memory_exporter = MemoryExporter()


_tracer_instance = None


def get_otel_tracer(name):
    global _tracer_instance
    if _tracer_instance is None:
        provider = get_tracer_provider()
        if isinstance(provider, ProxyTracerProvider):
            # Usually the tracer provider is set by the user in the SDK side.
            # If the user did not set the tracer provider, it will return a ProxyTracerProvider.
            # It can't be used to do span operations.
            # For this case, we create a default provider and set it as the global tracer provider.
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
        processor = SimpleSpanProcessor(memory_exporter)
        provider.add_span_processor(processor)

        connection_string = os.environ.get("APPINSIGHTS_CONNECTION_STRING")
        if connection_string:
            processor = BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=connection_string))
            provider.add_span_processor(processor)
        else:
            raise ValueError("connection_string is not set")

        _tracer_instance = get_tracer(name, tracer_provider=provider)

    return _tracer_instance
