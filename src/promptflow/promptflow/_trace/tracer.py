# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class Tracer:
    def __init__(self, otlp_port: str):
        self._trace_endpoint = f"http://localhost:{otlp_port}/v1/traces"
        self._init_otel_exporter()

    def _init_otel_exporter(self) -> None:
        otlp_span_exporter = OTLPSpanExporter(self._trace_endpoint)
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
