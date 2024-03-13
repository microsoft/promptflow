# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter


class MemoryExporter(SpanExporter):
    """An open telemetry span exporter to MDC."""

    def __init__(self):
        self.spans = []

    def export(self, spans: Sequence[ReadableSpan]):
        """export open telemetry spans to MDC."""
        self.spans.extend(spans)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Hint to ensure that the export of any spans the exporter has received
        prior to the call to ForceFlush SHOULD be completed as soon as possible, preferably
        before returning from this method.
        """
        return True
