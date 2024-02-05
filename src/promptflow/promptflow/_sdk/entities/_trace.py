# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import datetime
import json
import typing
from dataclasses import dataclass

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._constants import (
    DEFAULT_SESSION_ID,
    DEFAULT_SPAN_TYPE,
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanFieldName,
    SpanStatusFieldName,
)
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
        # `session_id` and `span_type` are not standard fields in OpenTelemetry attributes
        # for example, LangChain instrumentation, as we do not inject this;
        # so we need to get them with default value to avoid KeyError
        span_type = attributes.get(SpanAttributeFieldName.SPAN_TYPE, DEFAULT_SPAN_TYPE)
        # note that this might make these spans persisted in another partion if we split the trace table by `session_id`
        session_id = attributes.get(SpanAttributeFieldName.SESSION_ID, DEFAULT_SESSION_ID)

        return Span(
            name=obj.name,
            context=context,
            kind=obj.kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=attributes,
            resource=resource,
            span_type=span_type,
            session_id=session_id,
            parent_span_id=parent_span_id,
        )


@dataclass
class _LineRunData:
    """Basic data structure for line run, no matter if it is a main or evaluation."""

    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: typing.Dict
    outputs: typing.Dict
    start_time: datetime.datetime
    end_time: datetime.datetime
    status: str
    latency: float
    name: str
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]]

    def _from_root_span(span: Span) -> "_LineRunData":
        attributes: dict = span._content[SpanFieldName.ATTRIBUTES]
        if SpanAttributeFieldName.LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
        elif SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
        else:
            # eager flow/arbitrary script
            line_run_id = span.trace_id
        start_time = datetime.datetime.fromisoformat(span._content[SpanFieldName.START_TIME])
        end_time = datetime.datetime.fromisoformat(span._content[SpanFieldName.END_TIME])
        # calculate `cumulative_token_count`
        completion_token_count = int(attributes.get(SpanAttributeFieldName.COMPLETION_TOKEN_COUNT, 0))
        prompt_token_count = int(attributes.get(SpanAttributeFieldName.PROMPT_TOKEN_COUNT, 0))
        total_token_count = int(attributes.get(SpanAttributeFieldName.TOTAL_TOKEN_COUNT, 0))
        # if there is no token usage, set `cumulative_token_count` to None
        if total_token_count > 0:
            cumulative_token_count = {
                "completion": completion_token_count,
                "prompt": prompt_token_count,
                "total": total_token_count,
            }
        else:
            cumulative_token_count = None
        return _LineRunData(
            line_run_id=line_run_id,
            trace_id=span.trace_id,
            root_span_id=span.span_id,
            # for standard OpenTelemetry traces, there won't be `inputs` and `outputs` in attributes
            inputs=json.loads(attributes.get(SpanAttributeFieldName.INPUTS, "{}")),
            outputs=json.loads(attributes.get(SpanAttributeFieldName.OUTPUT, "{}")),
            start_time=start_time,
            end_time=end_time,
            status=span._content[SpanFieldName.STATUS][SpanStatusFieldName.STATUS_CODE],
            latency=(end_time - start_time).total_seconds(),
            name=span.name,
            kind=attributes.get(SpanAttributeFieldName.SPAN_TYPE, span.span_type),
            cumulative_token_count=cumulative_token_count,
        )


@dataclass
class LineRun:
    """Line run is an abstraction of spans related to prompt flow."""

    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: typing.Dict
    outputs: typing.Dict
    start_time: str
    end_time: str
    status: str
    latency: float
    name: str
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]] = None
    evaluations: typing.Optional[typing.List[typing.Dict]] = None

    @staticmethod
    def _from_spans(spans: typing.List[Span]) -> "LineRun":
        main_line_run_data: _LineRunData = None
        evaluation_line_run_data_dict = dict()
        for span in spans:
            if span.parent_span_id:
                continue
            attributes = span._content[SpanFieldName.ATTRIBUTES]
            if SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes:
                evaluation_line_run_data_dict[span.name] = _LineRunData._from_root_span(span)
            elif SpanAttributeFieldName.LINE_RUN_ID in attributes:
                main_line_run_data = _LineRunData._from_root_span(span)
            else:
                # eager flow/arbitrary script
                main_line_run_data = _LineRunData._from_root_span(span)
        evaluations = dict()
        for eval_name, eval_line_run_data in evaluation_line_run_data_dict.items():
            evaluations[eval_name] = eval_line_run_data
        return LineRun(
            line_run_id=main_line_run_data.line_run_id,
            trace_id=main_line_run_data.trace_id,
            root_span_id=main_line_run_data.root_span_id,
            inputs=main_line_run_data.inputs,
            outputs=main_line_run_data.outputs,
            start_time=main_line_run_data.start_time.isoformat(),
            end_time=main_line_run_data.end_time.isoformat(),
            status=main_line_run_data.status,
            latency=main_line_run_data.latency,
            name=main_line_run_data.name,
            kind=main_line_run_data.kind,
            cumulative_token_count=main_line_run_data.cumulative_token_count,
            evaluations=evaluations,
        )
