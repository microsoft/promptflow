import datetime
import json
import typing
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._constants import (
    RUNNING_LINE_RUN_STATUS,
    SpanAttributeFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
)
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._trace import Span

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()


def load_and_override_span_example(
    trace_id: str,
    span_id: str,
    parent_id: typing.Optional[str],
    line_run_id: str,
) -> typing.Dict:
    # load template span from local example file
    example_span_path = TEST_ROOT / "test_configs/traces/large-data-span-example.json"
    with open(example_span_path, mode="r", encoding="utf-8") as f:
        span_dict = json.load(f)
    # override field(s)
    span_dict["context"]["trace_id"] = trace_id
    span_dict["context"]["span_id"] = span_id
    span_dict["parent_id"] = parent_id
    span_dict["attributes"]["line_run_id"] = line_run_id
    return span_dict


def mock_span(
    trace_id: str,
    span_id: str,
    parent_id: typing.Optional[str],
    line_run_id: str,
) -> Span:
    span_dict = load_and_override_span_example(
        trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id
    )
    # type conversion for timestamp - required for Span constructor
    span_dict["start_time"] = datetime.datetime.fromisoformat(span_dict["start_time"])
    span_dict["end_time"] = datetime.datetime.fromisoformat(span_dict["end_time"])
    # create Span object
    return Span(
        name=span_dict["name"],
        trace_id=trace_id,
        span_id=span_id,
        parent_id=parent_id,
        context=span_dict["context"],
        kind=span_dict["kind"],
        start_time=span_dict["start_time"],
        end_time=span_dict["end_time"],
        status=span_dict["status"],
        attributes=span_dict["attributes"],
        links=span_dict["links"],
        events=span_dict["events"],
        resource=span_dict["resource"],
    )


def mock_span_for_delete_tests(
    run: typing.Optional[str] = None,
    collection: typing.Optional[str] = None,
    start_time: typing.Optional[datetime.datetime] = None,
) -> Span:
    span = mock_span(
        trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None, line_run_id=str(uuid.uuid4())
    )
    if run is not None:
        span.attributes.pop(SpanAttributeFieldName.LINE_RUN_ID)
        span.attributes[SpanAttributeFieldName.BATCH_RUN_ID] = run
        span.attributes[SpanAttributeFieldName.LINE_NUMBER] = 0  # always line 0
    if collection is not None:
        span.resource[SpanResourceFieldName.ATTRIBUTES][SpanResourceAttributesFieldName.COLLECTION] = collection
    if start_time is not None:
        span.start_time = start_time
    span._persist()
    return span


def assert_span_equals(span: Span, expected_span_dict: typing.Dict) -> None:
    span_dict = span._to_rest_object()
    # assert "external_event_data_uris" in span_dict and pop
    assert "external_event_data_uris" in span_dict
    span_dict.pop("external_event_data_uris")
    assert span_dict == expected_span_dict


@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceEntitiesAndOperations:
    def test_span_persist_and_gets(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        span = mock_span(trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id)
        span._persist()
        # trace operations - get span
        # eager load
        eager_load_span = pf.traces.get_span(trace_id=trace_id, span_id=span_id, lazy_load=False)
        expected_span_dict = load_and_override_span_example(
            trace_id=trace_id, span_id=span_id, parent_id=parent_id, line_run_id=line_run_id
        )
        assert_span_equals(eager_load_span, expected_span_dict)
        # lazy load (default)
        lazy_load_span = pf.traces.get_span(trace_id=trace_id, span_id=span_id)
        # events.attributes should be empty in lazy load mode
        for i in range(len(expected_span_dict["events"])):
            expected_span_dict["events"][i]["attributes"] = dict()
        assert_span_equals(lazy_load_span, expected_span_dict)

    def test_spans_persist_and_line_run_gets(self, pf: PFClient) -> None:
        trace_id = str(uuid.uuid4())
        non_root_span_id = str(uuid.uuid4())
        root_span_id = str(uuid.uuid4())
        line_run_id = str(uuid.uuid4())
        # non-root span
        span = mock_span(
            trace_id=trace_id,
            span_id=non_root_span_id,
            parent_id=root_span_id,
            line_run_id=line_run_id,
        )
        span._persist()
        running_line_run = pf.traces.get_line_run(line_run_id=line_run_id)
        expected_running_line_run_dict = {
            "line_run_id": line_run_id,
            "trace_id": trace_id,
            "root_span_id": None,
            "inputs": None,
            "outputs": None,
            "start_time": "2024-03-21T06:37:22.332582",
            "end_time": None,
            "status": RUNNING_LINE_RUN_STATUS,
            "duration": None,
            "name": None,
            "kind": None,
            "collection": TRACE_DEFAULT_COLLECTION,
            "cumulative_token_count": None,
            "parent_id": None,
            "run": None,
            "line_number": None,
            "experiment": None,
            "session_id": None,
            "evaluations": None,
        }
        assert running_line_run._to_rest_object() == expected_running_line_run_dict
        # root span
        span = mock_span(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_id=None,
            line_run_id=line_run_id,
        )
        span._persist()
        terminated_line_run = pf.traces.get_line_run(line_run_id=line_run_id)
        expected_terminated_line_run_dict = {
            "line_run_id": line_run_id,
            "trace_id": trace_id,
            "root_span_id": root_span_id,
            "inputs": {"input1": "value1", "input2": "value2"},
            "outputs": {"output1": "val1", "output2": "val2"},
            "start_time": "2024-03-21T06:37:22.332582",
            "end_time": "2024-03-21T06:37:26.445007",
            "status": "Ok",
            "duration": 4.112425,
            "name": "openai.resources.chat.completions.Completions.create",
            "kind": "LLM",
            "collection": TRACE_DEFAULT_COLLECTION,
            "cumulative_token_count": {
                "completion": 14,
                "prompt": 1497,
                "total": 1511,
            },
            "parent_id": None,
            "run": None,
            "line_number": None,
            "experiment": None,
            "session_id": None,
            "evaluations": None,
        }
        assert terminated_line_run._to_rest_object() == expected_terminated_line_run_dict

    def test_delete_traces_three_tables(self, pf: PFClient) -> None:
        # trace operation does not expose API for events and spans
        # so directly use ORM class to list and assert events and spans existence and deletion
        from promptflow._sdk._orm.trace import Event as ORMEvent
        from promptflow._sdk._orm.trace import LineRun as ORMLineRun
        from promptflow._sdk._orm.trace import Span as ORMSpan

        mock_run = str(uuid.uuid4())
        mock_span = mock_span_for_delete_tests(run=mock_run)
        # assert events, span and line_run are persisted
        assert len(ORMEvent.list(trace_id=mock_span.trace_id, span_id=mock_span.span_id)) == 2
        assert len(ORMSpan.list(trace_ids=[mock_span.trace_id])) == 1
        assert len(ORMLineRun.list(runs=[mock_run])) == 1
        # delete traces and assert all traces are deleted
        pf.traces.delete(run=mock_run)
        assert len(ORMEvent.list(trace_id=mock_span.trace_id, span_id=mock_span.span_id)) == 0
        assert len(ORMSpan.list(trace_ids=[mock_span.trace_id])) == 0
        assert len(ORMLineRun.list(runs=[mock_run])) == 0

    def test_delete_traces_with_run(self, pf: PFClient) -> None:
        mock_run = str(uuid.uuid4())
        mock_span_for_delete_tests(run=mock_run)
        assert len(pf.traces.list_line_runs(runs=[mock_run])) == 1
        pf.traces.delete(run=mock_run)
        assert len(pf.traces.list_line_runs(runs=[mock_run])) == 0

    def test_delete_traces_with_collection(self, pf: PFClient) -> None:
        mock_collection = str(uuid.uuid4())
        mock_span_for_delete_tests(collection=mock_collection)
        assert len(pf.traces.list_line_runs(collection=mock_collection)) == 1
        pf.traces.delete(collection=mock_collection)
        assert len(pf.traces.list_line_runs(collection=mock_collection)) == 0

    def test_delete_traces_with_collection_and_started_before(self, pf: PFClient) -> None:
        # mock some traces that start 2 days before, and delete those start 1 days before
        mock_start_time = datetime.datetime.now() - datetime.timedelta(days=2)
        collection1, collection2 = str(uuid.uuid4()), str(uuid.uuid4())
        mock_span_for_delete_tests(collection=collection1, start_time=mock_start_time)
        mock_span_for_delete_tests(collection=collection2, start_time=mock_start_time)
        assert (
            len(pf.traces.list_line_runs(collection=collection1)) == 1
            and len(pf.traces.list_line_runs(collection=collection2)) == 1
        )
        delete_query_time = datetime.datetime.now() - datetime.timedelta(days=1)
        pf.traces.delete(collection=collection1, started_before=delete_query_time.isoformat())
        # only collection1 traces are deleted
        assert (
            len(pf.traces.list_line_runs(collection=collection1)) == 0
            and len(pf.traces.list_line_runs(collection=collection2)) == 1
        )
        pf.traces.delete(collection=collection2, started_before=delete_query_time.isoformat())
        assert len(pf.traces.list_line_runs(collection=collection2)) == 0

    def test_delete_traces_dry_run(self, pf: PFClient) -> None:
        mock_run = str(uuid.uuid4())
        mock_span_for_delete_tests(run=mock_run)
        num_traces = pf.traces.delete(run=mock_run, dry_run=True)
        assert num_traces == 1


@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceWithDevKit:
    def test_flow_test_trace_enabled(self, pf: PFClient) -> None:
        import promptflow._sdk._orchestrator.test_submitter

        with patch.object(promptflow._sdk._orchestrator.test_submitter, "start_trace") as mock_start_trace:
            inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
            pf.test(flow=Path(f"{FLOWS_DIR}/web_classification").absolute(), inputs=inputs)
            assert mock_start_trace.call_count == 1

    def test_flow_test_single_node_trace_not_enabled(self, pf: PFClient) -> None:
        import promptflow._sdk._orchestrator.test_submitter

        with patch.object(promptflow._sdk._orchestrator.test_submitter, "start_trace") as mock_start_trace:
            pf.test(
                flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
                inputs={"fetch_url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g"},
                node="fetch_text_content_from_url",
            )
            assert mock_start_trace.call_count == 0
