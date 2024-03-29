import datetime

import pytest

from promptflow._sdk.entities._trace import Span as SpanEntity
from promptflow.azure._storage.cosmosdb.span import Span


@pytest.mark.unittest
class TestSpan:
    FAKE_CREATED_BY = {"oid": "fake_oid"}
    FAKE_COLLECTION_ID = "fake_collection_id"

    def test_to_dict(self):
        span = Span(
            SpanEntity(
                trace_id="0xacf2291a630af328da8fabd6bf49f653",
                span_id="0x9ded7ce65d5f7775",
                name="test",
                context={
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
                },
                kind="test",
                parent_id="test",
                start_time=datetime.datetime.fromisoformat("2022-01-01T00:00:00"),
                end_time=datetime.datetime.fromisoformat("2022-01-01T00:01:00"),
                status={},
                attributes={},
                events=[],
                links=[],
                resource={},
            ),
            collection_id=self.FAKE_COLLECTION_ID,
            created_by=self.FAKE_CREATED_BY,
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "2022-01-01T00:00:00",
            "end_time": "2022-01-01T00:01:00",
            "context": {
                "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                "span_id": "0x9ded7ce65d5f7775",
            },
            "id": "0x9ded7ce65d5f7775",
            "partition_key": "default",
            "collection_id": "fake_collection_id",
            "created_by": {"oid": "fake_oid"},
        }

        span = Span(
            SpanEntity(
                trace_id="0xacf2291a630af328da8fabd6bf49f653",
                span_id="0x9ded7ce65d5f7775",
                name="test",
                context={
                    "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                    "span_id": "0x9ded7ce65d5f7775",
                },
                kind="test",
                parent_id="test",
                start_time=datetime.datetime.fromisoformat("2022-01-01T00:00:00"),
                end_time=datetime.datetime.fromisoformat("2022-01-01T00:01:00"),
                status={},
                attributes={"line_run_id": "test_line_run_id"},
                events=[],
                links=[],
                resource={"collection": "test_session_id"},
            ),
            collection_id=self.FAKE_COLLECTION_ID,
            created_by=self.FAKE_CREATED_BY,
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "2022-01-01T00:00:00",
            "end_time": "2022-01-01T00:01:00",
            "attributes": {"line_run_id": "test_line_run_id"},
            "partition_key": "test_session_id",
            "context": {
                "trace_id": "0xacf2291a630af328da8fabd6bf49f653",
                "span_id": "0x9ded7ce65d5f7775",
            },
            "id": "0x9ded7ce65d5f7775",
            "partition_key": "test_session_id",
            "collection_id": "fake_collection_id",
            "created_by": {"oid": "fake_oid"},
            "resource": {"collection": "test_session_id"},
        }
