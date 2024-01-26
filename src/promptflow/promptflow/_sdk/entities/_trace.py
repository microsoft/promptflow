# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._utils import flatten_span_attributes


class Span:
    def __init__(
        self,
        span_id: str,
        name: str,
        span_type: str,
        trace_id: str,
        session_id: str,
        content: str,
        parent_span_id: typing.Optional[str] = None,
        path: typing.Optional[str] = None,
        run: typing.Optional[str] = None,
        experiment: typing.Optional[str] = None,
    ):
        self.id = span_id
        self.name = name
        self.type = span_type
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.session_id = session_id
        self.content = content
        self.path = path
        self.run = run
        self.experiment = experiment

    def _persist(self) -> None:
        self._to_orm_object().persist()

    @staticmethod
    def _from_orm_object(obj: ORMSpan) -> "Span":
        return Span(
            span_id=obj.span_id,
            trace_id=obj.trace_id,
            parent_id=obj.parent_id,
            experiment_name=obj.experiment_name,
            run_name=obj.run_name,
            path=obj.path,
            content=obj.content,
        )

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
        span_dict = json.loads(MessageToJson(obj))
        from pprint import pprint

        pprint(span_dict)
        span_id = obj.span_id.hex()
        trace_id = obj.trace_id.hex()
        parent_span_id = obj.parent_span_id.hex()
        span_dict["spanId"] = span_id
        span_dict["traceId"] = trace_id
        if parent_span_id:
            span_dict["parentSpanId"] = parent_span_id
        span_dict["attributes"] = flatten_span_attributes(span_dict["attributes"])
        return Span(
            span_id=span_id,
            name=obj.name,
            span_type="Function",
            trace_id=trace_id,
            session_id="8cffec9b-eda9-4dab-a321-4f94227c23cb",
            content=json.dumps(span_dict),
            parent_id=parent_span_id,
        )
