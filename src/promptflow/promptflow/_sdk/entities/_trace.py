# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import datetime
import heapq
import json
import typing
from dataclasses import dataclass

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan

from promptflow._constants import (
    RUNNING_LINE_RUN_STATUS,
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanEventFieldName,
    SpanFieldName,
    SpanLinkFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import CumulativeTokenCountFieldName
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._utils import (
    convert_time_unix_nano_to_timestamp,
    flatten_pb_attributes,
    json_loads_parse_const_as_str,
    parse_otel_span_status_code,
)


class Span:
    """Span is exactly the same as OpenTelemetry Span."""

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        context: typing.Dict[str, str],
        kind: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        status: str,
        resource: typing.Dict,
        parent_id: typing.Optional[str] = None,
        attributes: typing.Optional[typing.Dict[str, str]] = None,
        links: typing.Optional[typing.List] = None,
        events: typing.Optional[typing.List] = None,
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.name = name
        self.context = copy.deepcopy(context)
        self.kind = kind
        self.parent_id = parent_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.attributes = copy.deepcopy(attributes) if attributes is not None else dict()
        self.links = copy.deepcopy(links) if links is not None else list()
        self.events = copy.deepcopy(events) if events is not None else list()
        self.resource = copy.deepcopy(resource)

    def _persist(self) -> None:
        self._to_orm_object().persist()

    @staticmethod
    def _from_orm_object(obj: ORMSpan) -> "Span":
        return Span(
            trace_id=obj.trace_id,
            span_id=obj.span_id,
            name=obj.name,
            context=copy.deepcopy(obj.context),
            kind=obj.kind,
            parent_id=obj.parent_id,
            start_time=obj.start_time,
            end_time=obj.end_time,
            status=obj.status,
            attributes=copy.deepcopy(obj.attributes),
            links=copy.deepcopy(obj.links),
            events=copy.deepcopy(obj.events),
            resource=copy.deepcopy(obj.resource),
        )

    def _to_orm_object(self) -> ORMSpan:
        return ORMSpan(
            trace_id=self.trace_id,
            span_id=self.span_id,
            name=self.name,
            context=copy.deepcopy(self.context),
            kind=self.kind,
            parent_id=self.parent_id,
            start_time=self.start_time,
            end_time=self.end_time,
            status=self.status,
            attributes=copy.deepcopy(self.attributes) if len(self.attributes) > 0 else None,
            links=copy.deepcopy(self.links) if len(self.links) > 0 else None,
            events=copy.deepcopy(self.events) if len(self.events) > 0 else None,
            resource=copy.deepcopy(self.resource),
        )

    @staticmethod
    def _from_protobuf_events(obj: typing.List[PBSpan.Event]) -> typing.List[typing.Dict]:
        events = []
        if len(obj) == 0:
            return events
        for pb_event in obj:
            event_dict: dict = json.loads(MessageToJson(pb_event))
            event = {
                SpanEventFieldName.NAME: pb_event.name,
                # .isoformat() here to make this dumpable to JSON
                SpanEventFieldName.TIMESTAMP: convert_time_unix_nano_to_timestamp(pb_event.time_unix_nano).isoformat(),
                SpanEventFieldName.ATTRIBUTES: flatten_pb_attributes(
                    event_dict.get(SpanEventFieldName.ATTRIBUTES, dict())
                ),
            }
            events.append(event)
        return events

    @staticmethod
    def _from_protobuf_links(obj: typing.List[PBSpan.Link]) -> typing.List[typing.Dict]:
        links = []
        if len(obj) == 0:
            return links
        for pb_link in obj:
            link_dict: dict = json.loads(MessageToJson(pb_link))
            link = {
                SpanLinkFieldName.CONTEXT: {
                    SpanContextFieldName.TRACE_ID: pb_link.trace_id.hex(),
                    SpanContextFieldName.SPAN_ID: pb_link.span_id.hex(),
                    SpanContextFieldName.TRACE_STATE: pb_link.trace_state,
                },
                SpanLinkFieldName.ATTRIBUTES: flatten_pb_attributes(
                    link_dict.get(SpanLinkFieldName.ATTRIBUTES, dict())
                ),
            }
            links.append(link)
        return links

    @staticmethod
    def _from_protobuf_object(obj: PBSpan, resource: typing.Dict) -> "Span":
        # Open Telemetry does not provide official way to parse Protocol Buffer Span object
        # so we need to parse it manually relying on `MessageToJson`
        # reference: https://github.com/open-telemetry/opentelemetry-python/issues/3700#issuecomment-2010704554
        span_dict: dict = json.loads(MessageToJson(obj))
        span_id = obj.span_id.hex()
        trace_id = obj.trace_id.hex()
        parent_id = obj.parent_span_id.hex()
        # we have observed in some scenarios, there is not `attributes` field
        attributes = flatten_pb_attributes(span_dict.get(SpanFieldName.ATTRIBUTES, dict()))
        links = Span._from_protobuf_links(obj.links)
        events = Span._from_protobuf_events(obj.events)

        return Span(
            trace_id=trace_id,
            span_id=span_id,
            name=obj.name,
            context={
                SpanContextFieldName.TRACE_ID: trace_id,
                SpanContextFieldName.SPAN_ID: span_id,
                SpanContextFieldName.TRACE_STATE: obj.trace_state,
            },
            kind=obj.kind,
            parent_id=parent_id if parent_id else None,
            start_time=convert_time_unix_nano_to_timestamp(obj.start_time_unix_nano),
            end_time=convert_time_unix_nano_to_timestamp(obj.end_time_unix_nano),
            status={
                SpanStatusFieldName.STATUS_CODE: parse_otel_span_status_code(obj.status.code),
                SpanStatusFieldName.DESCRIPTION: obj.status.message,
            },
            attributes=attributes,
            links=links,
            events=events,
            resource=resource,
        )


@dataclass
class _LineRunData:
    """Basic data structure for line run, no matter if it is a main or evaluation."""

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
    display_name: str  # rename to `name`, keep this to avoid breaking before UX update
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]]

    def _from_root_span(span: Span) -> "_LineRunData":
        attributes: dict = span._content[SpanFieldName.ATTRIBUTES]
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
                CumulativeTokenCountFieldName.COMPLETION: completion_token_count,
                CumulativeTokenCountFieldName.PROMPT: prompt_token_count,
                CumulativeTokenCountFieldName.TOTAL: total_token_count,
            }
        else:
            cumulative_token_count = None
        return _LineRunData(
            line_run_id=line_run_id,
            trace_id=span.trace_id,
            root_span_id=span.span_id,
            # for standard OpenTelemetry traces, there won't be `inputs` and `outputs` in attributes
            inputs=json_loads_parse_const_as_str(attributes.get(SpanAttributeFieldName.INPUTS, "{}")),
            outputs=json_loads_parse_const_as_str(attributes.get(SpanAttributeFieldName.OUTPUT, "{}")),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            status=span._content[SpanFieldName.STATUS][SpanStatusFieldName.STATUS_CODE],
            latency=(end_time - start_time).total_seconds(),
            name=span.name,
            display_name=span.name,
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
    evaluations: typing.Optional[typing.Dict[str, _LineRunData]] = None

    @staticmethod
    def _generate_line_run_placeholder(spans: typing.List[Span]) -> "LineRun":
        # placeholder for traces whose root spans are absent
        # this placeholder will have trace id collected from other children spans
        # so that we can know more querying spans with trace id
        trace_id = spans[0].trace_id
        # leverage heap sort to get the earliest start time
        start_times = [datetime.datetime.fromisoformat(span._content[SpanFieldName.START_TIME]) for span in spans]
        earliest_start_time = heapq.nsmallest(1, start_times)[0]
        return LineRun(
            line_run_id=trace_id,
            trace_id=trace_id,
            root_span_id=None,
            inputs=None,
            outputs=None,
            start_time=earliest_start_time.isoformat(),
            end_time=None,
            status=RUNNING_LINE_RUN_STATUS,
            latency=None,
            name=None,
            kind=None,
            cumulative_token_count=None,
            evaluations=None,
        )

    @staticmethod
    def _from_spans(
        spans: typing.List[Span],
        run: typing.Optional[str] = None,
        trace_id: typing.Optional[str] = None,
    ) -> typing.Optional["LineRun"]:
        main_line_run_data: _LineRunData = None
        evaluations = dict()
        for span in spans:
            if span.parent_span_id:
                continue
            attributes = span._content[SpanFieldName.ATTRIBUTES]
            line_run_data = _LineRunData._from_root_span(span)
            # determine this line run data is the main or the eval
            if run is not None:
                # `run` is specified, this line run comes from a batch run
                batch_run_id = attributes[SpanAttributeFieldName.BATCH_RUN_ID]
                if batch_run_id == run:
                    main_line_run_data = line_run_data
                else:
                    evaluations[span.name] = line_run_data
            elif trace_id is not None:
                # `trace_id` is specified, if matched, this should be the main line run
                if trace_id == span.trace_id:
                    main_line_run_data = line_run_data
                else:
                    evaluations[span.name] = line_run_data
            else:
                if (
                    SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes
                    or SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID in attributes
                ):
                    evaluations[span.name] = line_run_data
                else:
                    main_line_run_data = line_run_data

        # main line run span is absent
        if main_line_run_data is None:
            if len(evaluations) == 0:
                # no eval traces, indicates the line is still executing
                # generate a placeholder line run for this WIP line
                return LineRun._generate_line_run_placeholder(spans)
            # otherwise, silently ignore
            return None

        return LineRun(
            line_run_id=main_line_run_data.line_run_id,
            trace_id=main_line_run_data.trace_id,
            root_span_id=main_line_run_data.root_span_id,
            inputs=main_line_run_data.inputs,
            outputs=main_line_run_data.outputs,
            start_time=main_line_run_data.start_time,
            end_time=main_line_run_data.end_time,
            status=main_line_run_data.status,
            latency=main_line_run_data.latency,
            name=main_line_run_data.name,
            kind=main_line_run_data.kind,
            cumulative_token_count=main_line_run_data.cumulative_token_count,
            evaluations=evaluations,
        )
