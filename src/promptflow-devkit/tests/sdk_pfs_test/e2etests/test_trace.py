# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import typing
import uuid

import pytest

from promptflow._constants import (
    RUNNING_LINE_RUN_STATUS,
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk.entities._trace import Span

from ..utils import PFSOperations


@pytest.fixture
def mock_collection() -> str:
    """Generate a collection for test case."""
    return str(uuid.uuid4())


def persist_a_span(
    collection: str,
    custom_attributes: typing.Optional[typing.Dict] = None,
    custom_events: typing.List[typing.Dict] = None,
    parent_id: typing.Optional[str] = None,
) -> Span:
    if custom_attributes is None:
        custom_attributes = {}
    trace_id = str(uuid.uuid4())
    span_id = str(uuid.uuid4())
    span = Span(
        trace_id=trace_id,
        span_id=span_id,
        name=str(uuid.uuid4()),
        context={
            SpanContextFieldName.TRACE_ID: trace_id,
            SpanContextFieldName.SPAN_ID: span_id,
            SpanContextFieldName.TRACE_STATE: "",
        },
        kind="1",
        parent_id=parent_id,
        start_time=datetime.datetime.now(),
        end_time=datetime.datetime.now(),
        status={
            SpanStatusFieldName.STATUS_CODE: "Ok",
        },
        attributes={
            SpanAttributeFieldName.FRAMEWORK: "promptflow",
            SpanAttributeFieldName.SPAN_TYPE: "Flow",
            **custom_attributes,
        },
        resource={
            "attributes": {
                "service.name": "promptflow",
                "collection": collection,
            },
            "schema_url": "",
        },
        events=custom_events,
    )
    span._persist()
    return span


# flask-restx uses marshmallow before response, so we do need this test class to execute end-to-end test
@pytest.mark.e2etest
class TestTrace:
    def test_cumulative_token_count_type(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        completion_token_count, prompt_token_count, total_token_count = 1, 5620, 5621
        token_count_attributes = {
            SpanAttributeFieldName.CUMULATIVE_COMPLETION_TOKEN_COUNT: completion_token_count,
            SpanAttributeFieldName.CUMULATIVE_PROMPT_TOKEN_COUNT: prompt_token_count,
            SpanAttributeFieldName.CUMULATIVE_TOTAL_TOKEN_COUNT: total_token_count,
        }
        persist_a_span(collection=mock_collection, custom_attributes=token_count_attributes)
        response = pfs_op.list_line_runs(collection=mock_collection)
        line_runs = response.json
        assert len(line_runs) == 1
        line_run = line_runs[0]
        cumulative_token_count = line_run[LineRunFieldName.CUMULATIVE_TOKEN_COUNT]
        assert isinstance(cumulative_token_count, dict)
        assert cumulative_token_count[CumulativeTokenCountFieldName.COMPLETION] == completion_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.PROMPT] == prompt_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.TOTAL] == total_token_count

    def test_evaluation_name(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        # mock batch run line
        mock_batch_run_id = str(uuid.uuid4())
        batch_run_attrs = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(collection=mock_collection, custom_attributes=batch_run_attrs)
        # mock eval run line
        mock_eval_run_id = str(uuid.uuid4())
        eval_run_attrs = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_eval_run_id,
            SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(collection=mock_collection, custom_attributes=eval_run_attrs)
        line_run = pfs_op.list_line_runs(runs=[mock_batch_run_id]).json[0]
        assert isinstance(line_run[LineRunFieldName.EVALUATIONS], dict)
        assert len(line_run[LineRunFieldName.EVALUATIONS]) == 1
        eval_line_run = list(line_run[LineRunFieldName.EVALUATIONS].values())[0]
        assert LineRunFieldName.NAME in eval_line_run

    def test_list_evaluation_line_runs(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_batch_run_id = str(uuid.uuid4())
        mock_referenced_batch_run_id = str(uuid.uuid4())
        batch_run_attributes = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: mock_referenced_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(collection=mock_collection, custom_attributes=batch_run_attributes)
        line_runs = pfs_op.list_line_runs(runs=[mock_batch_run_id]).json
        assert len(line_runs) == 1

    def test_list_eval_line_run_with_trace_id(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_batch_run = str(uuid.uuid4())
        mock_ref_batch_run = str(uuid.uuid4())
        batch_run_attrs = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run,
            SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: mock_ref_batch_run,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        span = persist_a_span(collection=mock_collection, custom_attributes=batch_run_attrs)
        line_runs = pfs_op.list_line_runs(trace_ids=[span.trace_id]).json
        assert len(line_runs) == 1

    def test_list_running_line_run(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_batch_run_id = str(uuid.uuid4())
        mock_parent_id = str(uuid.uuid4())
        batch_run_attributes = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(
            collection=mock_collection,
            custom_attributes=batch_run_attributes,
            parent_id=mock_parent_id,
        )
        line_runs = pfs_op.list_line_runs(runs=[mock_batch_run_id]).json
        assert len(line_runs) == 1
        running_line_run = line_runs[0]
        assert running_line_run[LineRunFieldName.STATUS] == RUNNING_LINE_RUN_STATUS

    def test_list_line_runs_with_both_status(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_batch_run_id = str(uuid.uuid4())
        # running line run
        mock_parent_id = str(uuid.uuid4())
        batch_run_attributes = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(
            collection=mock_collection,
            custom_attributes=batch_run_attributes,
            parent_id=mock_parent_id,
        )
        # completed line run
        batch_run_attributes = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "1",
        }
        persist_a_span(
            collection=mock_collection,
            custom_attributes=batch_run_attributes,
        )
        # we have slightly different code path for query w/o runs and w/ runs
        for line_runs in [
            pfs_op.list_line_runs(collection=mock_collection).json,
            pfs_op.list_line_runs(runs=[mock_batch_run_id]).json,
        ]:
            assert len(line_runs) == 2
            # according to order by logic, the first line run is line 1, the completed
            assert line_runs[0][LineRunFieldName.STATUS] == "Ok"
            assert line_runs[1][LineRunFieldName.STATUS] == RUNNING_LINE_RUN_STATUS

    def test_list_line_run_with_session_id(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_session_id = str(uuid.uuid4())
        custom_attributes = {SpanAttributeFieldName.SESSION_ID: mock_session_id}
        persist_a_span(collection=mock_collection, custom_attributes=custom_attributes)
        line_runs = pfs_op.list_line_runs(session_id=mock_session_id).json
        assert len(line_runs) == 1

    def test_list_line_run_with_line_run_id(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        mock_line_run_id = str(uuid.uuid4())
        custom_attributes = {SpanAttributeFieldName.LINE_RUN_ID: mock_line_run_id}
        persist_a_span(collection=mock_collection, custom_attributes=custom_attributes)
        line_runs = pfs_op.list_line_runs(line_run_ids=[mock_line_run_id]).json
        assert len(line_runs) == 1

    def test_search_line_run_with_invalid_expr(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.search_line_runs(expression="invalid expr")
        assert response.status_code == 400

    def test_basic_search_line_run(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        span = persist_a_span(collection=mock_collection)
        name = span.name
        line_runs = pfs_op.search_line_runs(expression=f"name == '{name}'").json
        assert len(line_runs) == 1

    def test_search_line_run_with_bool_op(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        span = persist_a_span(collection=mock_collection)
        line_runs = pfs_op.search_line_runs(expression=f"name == '{span.name}' and kind == 'Flow'").json
        assert len(line_runs) == 1

    def test_search_line_run_with_collection(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        # persist two spans/line runs, one w/ session and one w/o
        persist_a_span(collection=mock_collection)
        session_id = str(uuid.uuid4())
        custom_attributes = {SpanAttributeFieldName.SESSION_ID: session_id}
        persist_a_span(collection=mock_collection, custom_attributes=custom_attributes)
        # search with collection, should get 2 line runs
        line_runs = pfs_op.search_line_runs(expression="kind == 'Flow'", collection=mock_collection).json
        assert len(line_runs) == 2
        # search with collection and session_id, should get 1 line run
        line_runs = pfs_op.search_line_runs(expression="kind == 'Flow'", session_id=session_id).json

    def test_list_collections(self, pfs_op: PFSOperations, mock_collection: str) -> None:
        persist_a_span(collection=mock_collection)
        collections = pfs_op.list_collections().json
        assert len(collections) > 0
        collection = collections[0]
        assert isinstance(collection, dict) and "name" in collection and "update_time" in collection
