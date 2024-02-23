import pytest
from promptflow.azure._storage.cosmosdb.span import Span
from promptflow._sdk.entities._trace import Span as SpanEntity


@pytest.mark.unittest
class TestSpan:
    def test_to_dict(self):
        span = Span(
            SpanEntity(
                name="test",
                context={
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
                },
                kind="test",
                parent_span_id="test",
                start_time="test",
                end_time="test",
                status={},
                attributes={},
                events=[],
                links=[],
                resource={},
                span_type=None,
                session_id=None,

            )
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "test",
            "end_time": "test",
            "context": {
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
            },
            "id": "0x9ded7ce65d5f7775",
        }

        span = Span(
            SpanEntity(
                name="test",
                context={
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
                },
                kind="test",
                parent_span_id="test",
                start_time="test",
                end_time="test",
                status={},
                attributes={"line_run_id": "test_line_run_id"},
                events=[],
                links=[],
                resource={},
                span_type=None,
                session_id="test_session_id",
            )
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "test",
            "end_time": "test",
            "attributes": {"line_run_id": "test_line_run_id"},
            "partition_key": "test_session_id",
            "context": {
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
            },
            "id": "0x9ded7ce65d5f7775",
            "partition_key": "test_session_id",
        }