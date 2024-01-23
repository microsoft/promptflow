import json
import typing
import uuid

from model import Span


def generate_a_span(
    trace_id: typing.Optional[str] = None,
    parent_id: typing.Optional[str] = None,
    experiment_name: str = "default",
    run_name: typing.Optional[str] = None,
    path: typing.Optional[str] = None,
) -> Span:
    span_id = str(uuid.uuid4())
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    content = {
        "name": str(uuid.uuid4()),
        "context": {
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_state": "[]",
        },
        "kind": "SpanKind.INTERNAL",
        "parent_id": parent_id,
        "start_time": "2024-01-03T06:32:25.297521Z",
        "end_time": "2024-01-03T06:32:25.799009Z",
        "status": {
            "status_code": "UNSET",
        },
        "attributes": {
            "span_type": "Function",
            "experiment_name": experiment_name,
            "run_name": run_name,
            "path": path,
            # we need a 5KB JSON, so add below field
            "placeholder": "value" * 1024,
        },
        "events": [],
        "links": [],
        "resource": {
            "attributes": {
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version": "1.22.0",
                "service.name": "unknown_service",
            },
            "schema_url": "",
        }
    }
    return Span(
        span_id=span_id,
        trace_id=trace_id,
        parent_id=parent_id,
        experiment_name=experiment_name,
        run_name=run_name,
        path=path,
        content=json.dumps(content),
    )


def prepare_database(N: int) -> None:
    # N runs in partition (a database file)
    # 10K lines (parent span) per run
    # 10 spans (sub span) per line
    # 5KB content per span
    for _ in range(N):
        # run-level
        for _ in range(10000):
            # line-level, inside one trace
            trace_id = str(uuid.uuid4())
            parent_span = generate_a_span(trace_id=trace_id)
            parent_span_id = parent_span.span_id
            parent_span.persist()
            for _ in range(10):
                sub_span = generate_a_span(
                    trace_id=trace_id, parent_id=parent_span_id
                )
                sub_span.persist()
