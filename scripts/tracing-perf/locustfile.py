import uuid

from locust import HttpUser, between, task
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import Span, TracerProvider

trace.set_tracer_provider(TracerProvider())


class PromptFlowServiceTracingAPI:
    OTLP_COLLECTOR = "/v1/traces"
    LIST_SPANS = "/v1.0/Spans/list"
    LIST_LINE_RUNS = "/v1.0/LineRuns/list"


def create_span() -> Span:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(str(uuid.uuid4())) as span:
        pass
    return span


class TracingUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def heartbeat(self):
        self.client.get("/heartbeat")

    @task
    def collect_trace(self):
        spans = [create_span()]
        serialized_data = encode_spans(spans).SerializeToString()
        headers = {"Content-Type": "application/x-protobuf"}
        self.client.post(
            PromptFlowServiceTracingAPI.OTLP_COLLECTOR,
            data=serialized_data,
            headers=headers,
        )
