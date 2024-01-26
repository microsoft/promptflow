# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import Span


class TraceOperations:
    def get(self, span_id: str) -> Span:
        return Span._from_orm_object(ORMSpan.get(span_id=span_id))

    def list(self) -> typing.List[Span]:
        orm_spans = ORMSpan.list()
        return [Span._from_orm_object(orm_span) for orm_span in orm_spans]
