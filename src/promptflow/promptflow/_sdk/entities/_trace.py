# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import datetime
import json
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._constants import SpanAttributeFieldName, SpanContextFieldName, SpanFieldName, SpanStatusFieldName
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._utils import (
    convert_time_unix_nano_to_timestamp,
    flatten_pb_attributes,
    parse_otel_span_status_code,
)


class Span:
    """Span is exactly the same as OpenTelemetry Span."""

    def __init__(
        self,
        name: str,
        context: typing.Dict[str, str],
        kind: str,
        start_time: str,
        end_time: str,
        status: str,
        attributes: typing.Dict[str, str],
        resource: typing.Dict,
        # should come from attributes
        span_type: str,
        session_id: str,
        # optional fields
        parent_span_id: typing.Optional[str] = None,
        events: typing.Optional[typing.List] = None,
        links: typing.Optional[typing.List] = None,
        # prompt flow concepts
        path: typing.Optional[str] = None,
        run: typing.Optional[str] = None,
        experiment: typing.Optional[str] = None,
    ):
        self.name = name
        self.span_id = context[SpanContextFieldName.SPAN_ID]
        self.trace_id = context[SpanContextFieldName.TRACE_ID]
        self.span_type = span_type
        self.parent_span_id = parent_span_id
        self.session_id = session_id
        self.path = path
        self.run = run
        self.experiment = experiment
        self._content = {
            SpanFieldName.NAME: self.name,
            SpanFieldName.CONTEXT: copy.deepcopy(context),
            SpanFieldName.KIND: kind,
            SpanFieldName.PARENT_ID: self.parent_span_id,
            SpanFieldName.START_TIME: start_time,
            SpanFieldName.END_TIME: end_time,
            SpanFieldName.STATUS: status,
            SpanFieldName.ATTRIBUTES: copy.deepcopy(attributes),
            SpanFieldName.EVENTS: copy.deepcopy(events),
            SpanFieldName.LINKS: copy.deepcopy(links),
            SpanFieldName.RESOURCE: copy.deepcopy(resource),
        }

    def _persist(self) -> None:
        self._to_orm_object().persist()

    @staticmethod
    def _from_orm_object(obj: ORMSpan) -> "Span":
        content = json.loads(obj.content)
        return Span(
            name=obj.name,
            context=content[SpanFieldName.CONTEXT],
            kind=content[SpanFieldName.KIND],
            start_time=content[SpanFieldName.START_TIME],
            end_time=content[SpanFieldName.END_TIME],
            status=content[SpanFieldName.STATUS],
            attributes=content[SpanFieldName.ATTRIBUTES],
            resource=content[SpanFieldName.RESOURCE],
            span_type=obj.span_type,
            session_id=obj.session_id,
            parent_span_id=obj.parent_span_id,
            events=content[SpanFieldName.EVENTS],
            links=content[SpanFieldName.LINKS],
            path=obj.path,
            run=obj.run,
            experiment=obj.experiment,
        )

    def _to_orm_object(self) -> ORMSpan:
        return ORMSpan(
            name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            span_type=self.span_type,
            session_id=self.session_id,
            content=json.dumps(self._content),
            path=self.path,
            run=self.run,
            experiment=self.experiment,
        )

    @staticmethod
    def _from_protobuf_object(obj: PBSpan, resource: typing.Dict) -> "Span":
        span_dict = json.loads(MessageToJson(obj))
        span_id = obj.span_id.hex()
        trace_id = obj.trace_id.hex()
        context = {
            SpanContextFieldName.TRACE_ID: trace_id,
            SpanContextFieldName.SPAN_ID: span_id,
            SpanContextFieldName.TRACE_STATE: obj.trace_state,
        }
        parent_span_id = obj.parent_span_id.hex()
        start_time = convert_time_unix_nano_to_timestamp(obj.start_time_unix_nano)
        end_time = convert_time_unix_nano_to_timestamp(obj.end_time_unix_nano)
        status = {
            SpanStatusFieldName.STATUS_CODE: parse_otel_span_status_code(obj.status.code),
        }
        attributes = flatten_pb_attributes(span_dict[SpanFieldName.ATTRIBUTES])
        return Span(
            name=obj.name,
            context=context,
            kind=obj.kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=attributes,
            resource=resource,
            span_type=attributes[SpanAttributeFieldName.SPAN_TYPE],
            session_id=attributes[SpanAttributeFieldName.SESSION_ID],
            parent_span_id=parent_span_id,
        )


class LineRun:
    """Line run is an abstraction of spans related to prompt flow."""

    def __init__(
        self,
        line_run_id: str,
        inputs: typing.Dict,
        outputs: typing.Dict,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        status: str,
        latency: float,
        name: str,
        kind: str,
        cumulative_token_count: typing.Dict[str, int],
        evaluations: typing.Optional[typing.List[typing.Dict]] = None,
    ):
        ...
