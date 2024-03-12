# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import typing
import uuid

import pytest

from promptflow._constants import SpanAttributeFieldName, SpanContextFieldName, SpanStatusFieldName
from promptflow._sdk._constants import CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk.entities._trace import Span

from ..utils import PFSOperations


@pytest.fixture
def mock_session_id() -> str:
    """Generate a session id for test case."""
    return str(uuid.uuid4())


def persist_a_span(session_id: str, custom_attributes: typing.Optional[typing.Dict] = None) -> None:
    if custom_attributes is None:
        custom_attributes = {}
    span = Span(
        name=str(uuid.uuid4()),
        context={
            SpanContextFieldName.TRACE_ID: str(uuid.uuid4()),
            SpanContextFieldName.SPAN_ID: str(uuid.uuid4()),
            SpanContextFieldName.TRACE_STATE: "",
        },
        kind="1",
        start_time=datetime.datetime.now().isoformat(),
        end_time=datetime.datetime.now().isoformat(),
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
                "session.id": session_id,
            },
            "schema_url": "",
        },
        span_type="Flow",
        session_id=session_id,
    )
    span._persist()
    return


# flask-restx uses marshmallow before response, so we do need this test class to execute end-to-end test
@pytest.mark.e2etest
class TestTrace:
    def test_cumulative_token_count_type(self, pfs_op: PFSOperations, mock_session_id: str) -> None:
        completion_token_count, prompt_token_count, total_token_count = 1, 5620, 5621
        token_count_attributes = {
            SpanAttributeFieldName.CUMULATIVE_COMPLETION_TOKEN_COUNT: completion_token_count,
            SpanAttributeFieldName.CUMULATIVE_PROMPT_TOKEN_COUNT: prompt_token_count,
            SpanAttributeFieldName.CUMULATIVE_TOTAL_TOKEN_COUNT: total_token_count,
        }
        persist_a_span(session_id=mock_session_id, custom_attributes=token_count_attributes)
        response = pfs_op.list_line_runs(session_id=mock_session_id)
        line_runs = response.json
        assert len(line_runs) == 1
        line_run = line_runs[0]
        cumulative_token_count = line_run[LineRunFieldName.CUMULATIVE_TOKEN_COUNT]
        assert isinstance(cumulative_token_count, dict)
        assert cumulative_token_count[CumulativeTokenCountFieldName.COMPLETION] == completion_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.PROMPT] == prompt_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.TOTAL] == total_token_count

    def test_evaluation_type(self, pfs_op: PFSOperations, mock_session_id: str) -> None:
        persist_a_span(session_id=mock_session_id)
        response = pfs_op.list_line_runs(session_id=mock_session_id)
        line_run = response.json[0]
        assert isinstance(line_run[LineRunFieldName.EVALUATIONS], dict)

    def test_illegal_json_values(self, pfs_op: PFSOperations, mock_session_id: str) -> None:
        output_string = json.dumps(
            {
                "NaN": float("nan"),
                "Inf": float("inf"),
                "-Inf": float("-inf"),
            }
        )
        custom_attributes = {SpanAttributeFieldName.OUTPUT: output_string}
        persist_a_span(session_id=mock_session_id, custom_attributes=custom_attributes)
        line_run = pfs_op.list_line_runs(session_id=mock_session_id).json[0]
        output = line_run[LineRunFieldName.OUTPUTS]
        assert isinstance(output["NaN"], str) and output["NaN"] == "NaN"
        assert isinstance(output["Inf"], str) and output["Inf"] == "Infinity"
        assert isinstance(output["-Inf"], str) and output["-Inf"] == "-Infinity"

    def test_list_evaluation_line_runs(self, pfs_op: PFSOperations, mock_session_id: str) -> None:
        mock_batch_run_id = str(uuid.uuid4())
        mock_referenced_batch_run_id = str(uuid.uuid4())
        batch_run_attributes = {
            SpanAttributeFieldName.BATCH_RUN_ID: mock_batch_run_id,
            SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: mock_referenced_batch_run_id,
            SpanAttributeFieldName.LINE_NUMBER: "0",
        }
        persist_a_span(session_id=mock_session_id, custom_attributes=batch_run_attributes)
        line_runs = pfs_op.list_line_runs(runs=[mock_batch_run_id]).json
        assert len(line_runs) == 1
