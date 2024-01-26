# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class Tracer:
    def __init__(self):
        self._init_otel_exporter()

    def _init_otel_exporter(self) -> None:
        otlp_span_exporter = OTLPSpanExporter(
            # TODO: replace below hard code one with something from self
            endpoint="http://localhost:55507/v1/traces",
        )
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
        trace.set_tracer_provider(trace_provider)

    def trace(span: typing.Dict) -> None:
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("print") as span:
            print("foo")
            span.set_attribute("printed_string", "foo")


def _get_tracer() -> Tracer:
    # return the global singleton tracer
    ...
