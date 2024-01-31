# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import Span, Trace


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

    def list_traces(
        self,
        session_id: typing.Optional[str] = None,
    ) -> typing.List[Trace]:
        # TODO: do we need to leverage SQL during extraction
        ...
