# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import typing

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import LineRun, Span


class TraceOperations:
    def list_spans(
        self,
        session_id: typing.Optional[str] = None,
    ) -> typing.List[Span]:
        orm_spans = ORMSpan.list(
            session_id=session_id,
        )
        return [Span._from_orm_object(orm_span) for orm_span in orm_spans]

    def list_line_runs(
        self,
        session_id: typing.Optional[str] = None,
    ) -> typing.List[LineRun]:
        line_runs = []
        orm_spans_group_by_trace_id = ORMLineRun.list(session_id=session_id)
        # merge spans with same `line_run_id` or `referenced.line_run_id` (if exists)
        grouped_orm_spans = {}
        for orm_spans in orm_spans_group_by_trace_id:
            first_orm_span = orm_spans[0]
            attributes = json.loads(first_orm_span.content)[SpanFieldName.ATTRIBUTES]
            if (
                SpanAttributeFieldName.LINE_RUN_ID not in attributes
                and SpanAttributeFieldName.REFERENCED_LINE_RUN_ID not in attributes
            ):
                # no `line_run_id` or `referenced.line_run_id` in attributes
                # standard OpenTelemetry trace, regard as a line run
                grouped_orm_spans[first_orm_span.trace_id] = copy.deepcopy(orm_spans)
            elif (
                SpanAttributeFieldName.LINE_RUN_ID in attributes
                and SpanAttributeFieldName.REFERENCED_LINE_RUN_ID not in attributes
            ):
                # main flow trace
                line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
                if line_run_id not in grouped_orm_spans:
                    grouped_orm_spans[line_run_id] = []
                grouped_orm_spans[line_run_id].extend(copy.deepcopy(orm_spans))
            elif (
                SpanAttributeFieldName.LINE_RUN_ID in attributes
                and SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes
            ):
                # evaluation flow trace
                referenced_line_run_id = attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
                if referenced_line_run_id not in grouped_orm_spans:
                    grouped_orm_spans[referenced_line_run_id] = []
                grouped_orm_spans[referenced_line_run_id].extend(copy.deepcopy(orm_spans))
            else:
                # aggregation node, ignore for now
                pass
        for orm_spans in grouped_orm_spans.values():
            spans = [Span._from_orm_object(orm_span) for orm_span in orm_spans]
            line_runs.append(LineRun._from_spans(spans))
        return line_runs
