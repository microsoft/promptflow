# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._sdk._orm.otel import Span as ORMSpan


class Span:
    def __init__(
        self,
        span_id: str,
        trace_id: str,
        parent_id: typing.Optional[str] = None,
        experiment_name: typing.Optional[str] = None,
        run_name: typing.Optional[str] = None,
        path: typing.Optional[str] = None,
        content: typing.Optional[str] = None,
    ):
        self.span_id = span_id
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.experiment_name = experiment_name
        self.run_name = run_name
        self.path = path
        self.content = content

    def persist(self) -> None:
        self._to_orm_object().persist()

    def _to_orm_object(self) -> ORMSpan:
        return ORMSpan(
            span_id=self.span_id,
            trace_id=self.trace_id,
            parent_id=self.parent_id,
            experiment_name=self.experiment_name,
            run_name=self.run_name,
            path=self.path,
            content=self.content,
        )

    @staticmethod
    def _from_protobuf_object(obj: PBSpan) -> "Span":
        span_string = MessageToJson(obj)
        span_dict = json.loads(span_string)
        return Span(
            span_id=span_dict["spanId"],
            trace_id=span_dict["traceId"],
            parent_id=span_dict.get("parentSpanId"),
            content=span_string,
        )
