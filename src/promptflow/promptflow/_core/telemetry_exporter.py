import json
from typing import Sequence

from opentelemetry.sdk.trace.export import ReadableSpan, SpanExporter, SpanExportResult


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
