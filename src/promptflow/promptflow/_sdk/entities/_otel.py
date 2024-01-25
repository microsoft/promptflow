# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._sdk._orm.otel import Span as ORMSpan


class Span:
    def __init__(self):
        ...

    def _to_orm_object(self) -> ORMSpan:
        return ORMSpan()
