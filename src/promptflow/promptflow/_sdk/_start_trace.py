# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._sdk._constants import TRACE_SESSION_ID_ENV_VAR


def start_trace():
    # detect PFS liveness
    pfs_port = "55507"  # TODO: make this dynamic from PFS liveness probe
    # provision a session
    _provision_session()
    # init the global tracer with endpoint, context (session, run, exp)
    _init_otel_trace_exporter(otlp_port=pfs_port)
    # print user the UI url


def _provision_session() -> str:
    session_id = str(uuid.uuid4())
    # TODO: need to confirm if it can be inherited by subprocess
    os.environ[TRACE_SESSION_ID_ENV_VAR] = session_id
    return session_id


def _init_otel_trace_exporter(otlp_port: str) -> None:
    endpoint = f"http://localhost:{otlp_port}/v1/traces"
    otlp_span_exporter = OTLPSpanExporter(endpoint=endpoint)
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(trace_provider)
