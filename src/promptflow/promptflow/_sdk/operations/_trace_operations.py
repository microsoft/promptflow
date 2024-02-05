# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import LineRun, Span


class TraceOperations:
    def list_spans(
        self,
        session_id: typing.Optional[str] = None,
        parent_span_id: typing.Optional[str] = None,
    ) -> typing.List[Span]:
        orm_spans = ORMSpan.list(
            session_id=session_id,
            parent_span_id=parent_span_id,
        )
        return [Span._from_orm_object(orm_span) for orm_span in orm_spans]

    def list_line_runs(
        self,
        session_id: typing.Optional[str] = None,
    ) -> typing.List[LineRun]:
        orm_spans_group_by_trace_id = ORMLineRun.list(session_id=session_id)
        spans = [Span._from_orm_object(orm_span) for orm_spans in orm_spans_group_by_trace_id for orm_span in orm_spans]
        return LineRun._from_spans(spans)
