import datetime
import typing
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from mock import mock

from promptflow._constants import SpanAttributeFieldName, SpanContextFieldName, SpanStatusFieldName
from promptflow._sdk._constants import TRACE_DEFAULT_SESSION_ID
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._trace import Span

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()


def persist_a_span(
    session_id: str = TRACE_DEFAULT_SESSION_ID,
    run: typing.Optional[str] = None,
    start_time: typing.Optional[str] = None,
):
    span = Span(
        name=str(uuid.uuid4()),
        context={
            SpanContextFieldName.TRACE_ID: str(uuid.uuid4()),
            SpanContextFieldName.SPAN_ID: str(uuid.uuid4()),
            SpanContextFieldName.TRACE_STATE: "",
        },
        kind="1",
        start_time=datetime.datetime.now().isoformat() if start_time is None else start_time,
        end_time=datetime.datetime.now().isoformat(),
        status={
            SpanStatusFieldName.STATUS_CODE: "Ok",
        },
        attributes={
            SpanAttributeFieldName.FRAMEWORK: "promptflow",
            SpanAttributeFieldName.SPAN_TYPE: "Flow",
        },
        resource={
            "attributes": {
                "service.name": "promptflow",
                "session.id": session_id,
            },
            "schema_url": "",
        },
        span_type="Flow",
        session_id=session_id,
        run=run,
    )
    span._persist()


@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceWithDevKit:
    def test_flow_test_trace_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
                pf.test(flow=Path(f"{FLOWS_DIR}/web_classification").absolute(), inputs=inputs)
                assert mock_start_trace.call_count == 1

    def test_flow_test_single_node_trace_not_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                pf.test(
                    flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
                    inputs={"fetch_url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g"},
                    node="fetch_text_content_from_url",
                )
                assert mock_start_trace.call_count == 0


@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceOperations:
    def test_delete_traces_with_run(self, pf: PFClient) -> None:
        mock_run = str(uuid.uuid4())
        num_spans = 3
        for _ in range(num_spans):
            persist_a_span(run=mock_run)
        row_cnt = pf._traces.delete(run=mock_run)
        assert row_cnt == num_spans

    def test_delete_traces_with_session(self, pf: PFClient) -> None:
        mock_session_id = str(uuid.uuid4())
        num_spans = 3
        for _ in range(num_spans):
            persist_a_span(session_id=mock_session_id)
        row_cnt = pf._traces.delete(session=mock_session_id)
        assert row_cnt == num_spans

    def test_delete_traces_with_session_and_started_before(self, pf: PFClient) -> None:
        # mock some traces that start 2 days before, and delete those start 1 days before
        mock_start_time = (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat()
        num_spans = 3
        session1, session2 = str(uuid.uuid4()), str(uuid.uuid4())
        for _ in range(num_spans):
            persist_a_span(session_id=session1, start_time=mock_start_time)
            persist_a_span(session_id=session2, start_time=mock_start_time)
        delete_query_time = datetime.datetime.now() - datetime.timedelta(days=1)
        row_cnt1 = pf._traces.delete(session=session1, started_before=delete_query_time.isoformat())
        row_cnt2 = pf._traces.delete(session=session2, started_before=delete_query_time.isoformat())
        assert row_cnt1 == num_spans
        assert row_cnt2 == num_spans
