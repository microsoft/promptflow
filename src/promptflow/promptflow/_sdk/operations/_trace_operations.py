# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import Span


class TraceOperations:
    def get_span(self, span_id: str) -> Span:
        return ORMSpan.get(span_id=span_id)
