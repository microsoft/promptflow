# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import Span


class TraceOperations:
    def list(
        self,
        parent_id: typing.Optional[str] = None,
    ) -> typing.List[Span]:
        orm_spans = ORMSpan.list()
        return [Span._from_orm_object(orm_span) for orm_span in orm_spans]
