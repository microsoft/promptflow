# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import uuid

import pytest

from promptflow._constants import SpanAttributeFieldName, SpanContextFieldName, SpanStatusFieldName
from promptflow._sdk._constants import CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk.entities._trace import Span

from ..utils import PFSOperations


# flask-restx uses marshmallow before response, so we do need this test class to execute end-to-end test
@pytest.mark.e2etest
class TestTrace:
    def test_cumulative_token_count_type(self, pfs_op: PFSOperations) -> None:
        completion_token_count, prompt_token_count, total_token_count = 1, 5620, 5621
        # generate a session id for this test
        session_id = str(uuid.uuid4())
        # insert a root span, so that we can list line run from that later
        mock_span = Span(
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
                # below attributes are mandatory for this test
                SpanAttributeFieldName.CUMULATIVE_COMPLETION_TOKEN_COUNT: completion_token_count,
                SpanAttributeFieldName.CUMULATIVE_PROMPT_TOKEN_COUNT: prompt_token_count,
                SpanAttributeFieldName.CUMULATIVE_TOTAL_TOKEN_COUNT: total_token_count,
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
        mock_span._persist()
        response = pfs_op.list_line_runs(session_id=session_id)
        line_runs = response.json
        assert len(line_runs) == 1
        line_run = line_runs[0]
        cumulative_token_count = line_run[LineRunFieldName.CUMULATIVE_TOKEN_COUNT]
        assert isinstance(cumulative_token_count, dict)
        assert cumulative_token_count[CumulativeTokenCountFieldName.COMPLETION] == completion_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.PROMPT] == prompt_token_count
        assert cumulative_token_count[CumulativeTokenCountFieldName.TOTAL] == total_token_count
