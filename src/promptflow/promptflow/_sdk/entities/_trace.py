# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._utils import convert_time_unix_nano_to_timestamp, flatten_pb_attributes


class Span:
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
        self.span_id = context["span_id"]
        self.trace_id = context["trace_id"]
        self.span_type = span_type
        self.parent_span_id = parent_span_id
        self.session_id = session_id
        self.path = path
        self.run = run
        self.experiment = experiment
        # use @dataclass
        self._content = {
            "name": self.name,
            "context": copy.deepcopy(context),
            "kind": kind,
            "parent_id": self.parent_span_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "attributes": copy.deepcopy(attributes),
            "events": copy.deepcopy(events),
            "links": copy.deepcopy(links),
            "resource": copy.deepcopy(resource),
        }

    def _persist(self) -> None:
        self._to_orm_object().persist()

    @staticmethod
    def _from_orm_object(obj: ORMSpan) -> "Span":
        content = json.loads(obj.content)
        return Span(
            name=obj.name,
            context=content["context"],
            kind=content["kind"],
            start_time=content["start_time"],
            end_time=content["end_time"],
            status=content["status"],
            attributes=content["attributes"],
            resource=content["resource"],
            span_type=obj.span_type,
            session_id=obj.session_id,
            parent_span_id=obj.parent_span_id,
            events=content["events"],
            links=content["links"],
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
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_state": obj.trace_state,
        }
        parent_span_id = obj.parent_span_id.hex()
        start_time = convert_time_unix_nano_to_timestamp(obj.start_time_unix_nano)
        end_time = convert_time_unix_nano_to_timestamp(obj.end_time_unix_nano)
        attributes = flatten_pb_attributes(span_dict["attributes"])
        return Span(
            name=obj.name,
            context=context,
            kind=obj.kind,
            start_time=start_time,
            end_time=end_time,
            # TODO: use real status
            # status=obj.status,
            status={"status_code": "OK"},
            attributes=attributes,
            resource=resource,
            span_type=attributes.get("span_type", "Function"),
            # TODO: get from env when it's set from our side
            # session_id=os.getenv(TRACE_SESSION_ID_ENV_VAR),
            session_id="8cffec9b-eda9-4dab-a321-4f94227c23cb",
            parent_span_id=parent_span_id,
        )
