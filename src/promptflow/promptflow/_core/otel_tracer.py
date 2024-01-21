import json
import os
from typing import Sequence

from opentelemetry.sdk.resources import SERVICE_NAME, Resource
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
from opentelemetry.trace import get_tracer, get_tracer_provider


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


class FileExporter(SpanExporter):
    def __init__(self, file_name="traces.json"):
        self.file_name = file_name
        # Open the file in append mode
        self.file = open(file_name, "a")

    def export(self, spans):
        # Convert spans to a format suitable for JSON serialization
        span_data = [span.to_json() for span in spans]
        # Write the JSON serialized span data to the file
        for span_json in span_data:
            self.file.write(span_json + "\n")
        self.file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        # Close the file when shutting down the exporter
        self.file.close()


class TreeConsoleSpanExporter:
    def __init__(self):
        # Dictionary to keep track of parent-child relationships
        self.span_tree = {}
        # Dictionary to keep track of span start times
        self.span_start_times = {}

    def export(self, spans):
        for span in spans:
            parent_id = span.parent.span_id if span.parent else None
            # Store the start time of the span for later use
            self.span_start_times[span.context.span_id] = span.start_time

            if parent_id not in self.span_tree:
                self.span_tree[parent_id] = []
            self.span_tree[parent_id].append(span)

        self._print_tree()

    def _print_tree(self, parent_id=None, level=0):
        if parent_id not in self.span_tree:
            return

        for span in self.span_tree[parent_id]:
            indent = "  " * level
            sections_to_print = [
                span.name,
                span.context.trace_id,
                span.context.span_id,
                span.end_time - span.start_time,
            ]
            print(f"{indent}- {' '.join(str(section) for section in sections_to_print)}")
            self._print_tree(span.context.span_id, level + 1)

    def shutdown(self):
        # Perform any cleanup if necessary
        pass


_tracer_instance = None


def get_otel_tracer(name):
    global _tracer_instance
    if _tracer_instance is None:
        resource = Resource(attributes={SERVICE_NAME: "promptflow"})
        provider = TracerProvider(resource=resource)

        processor = SimpleSpanProcessor(memory_exporter)
        provider.add_span_processor(processor)

        connection_string = os.environ.get("APPINSIGHTS_CONNECTION_STRING")
        if connection_string:
            processor = BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=connection_string))
            provider.add_span_processor(processor)
        else:
            # raise ValueError("connection_string is not set")
            pass

        provider.add_span_processor(SimpleSpanProcessor(FileExporter("traces.json")))

        provider.add_span_processor(SimpleSpanProcessor(TreeConsoleSpanExporter()))

        trace.set_tracer_provider(provider)

        _tracer_instance = get_tracer(name, tracer_provider=provider)

    return _tracer_instance
