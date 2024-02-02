import pytest
from promptflow.azure._storage.cosmosdb.span import Span

@pytest.mark.unittest
class TestSpan:
    def test_to_dict(self):
        span = Span(
            name="test",
            context={},
            kind="test",
            parent_id="test",
            start_time="test",
            end_time="test",
            status={},
            attributes={},
            events=[],
            links=[],
            resource={}
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "test",
            "end_time": "test"
        }

        span = Span(
            name="test",
            context={},
            kind="test",
            parent_id="test",
            start_time="test",
            end_time="test",
            status={},
            attributes={"line_run_id": "test_line_run_id", "session_id": "test_session_id"},
            events=[],
            links=[],
            resource={}
        )
        assert span.to_dict() == {
            "name": "test",
            "kind": "test",
            "parent_id": "test",
            "start_time": "test",
            "end_time": "test",
            "attributes": {"line_run_id": "test_line_run_id", "session_id": "test_session_id"},
            "id": "test_line_run_id",
            "partition_key": "test_session_id",
        }