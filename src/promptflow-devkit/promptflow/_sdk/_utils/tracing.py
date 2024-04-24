# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan
from opentelemetry.trace.span import format_span_id as otel_format_span_id
from opentelemetry.trace.span import format_trace_id as otel_format_trace_id

from promptflow._constants import (
    SpanContextFieldName,
    SpanEventFieldName,
    SpanFieldName,
    SpanLinkFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._utils import convert_time_unix_nano_to_timestamp
from promptflow._sdk.entities._trace import Span


def format_span_id(span_id: bytes) -> str:
    """Format span id to hex string.
    Note that we need to add 0x since it is how opentelemetry-sdk does.
    Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
    642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
    """
    return f"0x{otel_format_span_id(int.from_bytes(span_id, byteorder='big', signed=False))}"


def format_trace_id(trace_id: bytes) -> str:
    """Format trace_id id to hex string.
    Note that we need to add 0x since it is how opentelemetry-sdk does.
    Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
    642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
    """
    return f"0x{otel_format_trace_id(int.from_bytes(trace_id, byteorder='big', signed=False))}"


def parse_kv_from_pb_attribute(attribute: typing.Dict) -> typing.Tuple[str, str]:
    attr_key = attribute["key"]
    # suppose all values are flattened here
    # so simply regard the first value as the attribute value
    attr_value = list(attribute["value"].values())[0]
    return attr_key, attr_value


def _flatten_pb_attributes(attributes: typing.List[typing.Dict]) -> typing.Dict:
    flattened_attributes = {}
    for attribute in attributes:
        attr_key, attr_value = parse_kv_from_pb_attribute(attribute)
        flattened_attributes[attr_key] = attr_value
    return flattened_attributes


def _parse_otel_span_status_code(value: int) -> str:
    # map int value to string
    # https://github.com/open-telemetry/opentelemetry-specification/blob/v1.22.0/specification/trace/api.md#set-status
    # https://github.com/open-telemetry/opentelemetry-python/blob/v1.22.0/opentelemetry-api/src/opentelemetry/trace/status.py#L22-L32
    if value == 0:
        return "Unset"
    elif value == 1:
        return "Ok"
    else:
        return "Error"


def parse_protobuf_events(obj: typing.List[PBSpan.Event], logger: logging.Logger) -> typing.List[typing.Dict]:
    events = []
    if len(obj) == 0:
        logger.debug("No events found in span")
        return events
    for pb_event in obj:
        event_dict: dict = json.loads(MessageToJson(pb_event))
        logger.debug("Received event: %s", json.dumps(event_dict))
        event = {
            SpanEventFieldName.NAME: pb_event.name,
            # .isoformat() here to make this dumpable to JSON
            SpanEventFieldName.TIMESTAMP: convert_time_unix_nano_to_timestamp(pb_event.time_unix_nano).isoformat(),
            SpanEventFieldName.ATTRIBUTES: _flatten_pb_attributes(
                event_dict.get(SpanEventFieldName.ATTRIBUTES, dict())
            ),
        }
        events.append(event)
    return events


def parse_protobuf_links(obj: typing.List[PBSpan.Link], logger: logging.Logger) -> typing.List[typing.Dict]:
    links = []
    if len(obj) == 0:
        logger.debug("No links found in span")
        return links
    for pb_link in obj:
        link_dict: dict = json.loads(MessageToJson(pb_link))
        logger.debug("Received link: %s", json.dumps(link_dict))
        link = {
            SpanLinkFieldName.CONTEXT: {
                SpanContextFieldName.TRACE_ID: format_trace_id(pb_link.trace_id),
                SpanContextFieldName.SPAN_ID: format_span_id(pb_link.span_id),
                SpanContextFieldName.TRACE_STATE: pb_link.trace_state,
            },
            SpanLinkFieldName.ATTRIBUTES: _flatten_pb_attributes(link_dict.get(SpanLinkFieldName.ATTRIBUTES, dict())),
        }
        links.append(link)
    return links


def parse_protobuf_span(span: PBSpan, resource: typing.Dict, logger: logging.Logger) -> Span:
    # Open Telemetry does not provide official way to parse Protocol Buffer Span object
    # so we need to parse it manually relying on `MessageToJson`
    # reference: https://github.com/open-telemetry/opentelemetry-python/issues/3700#issuecomment-2010704554
    span_dict: dict = json.loads(MessageToJson(span))
    logger.debug("Received span: %s, resource: %s", json.dumps(span_dict), json.dumps(resource))
    span_id = format_span_id(span.span_id)
    trace_id = format_trace_id(span.trace_id)
    parent_id = format_span_id(span.parent_span_id) if span.parent_span_id else None
    # we have observed in some scenarios, there is not `attributes` field
    attributes = _flatten_pb_attributes(span_dict.get(SpanFieldName.ATTRIBUTES, dict()))
    logger.debug("Parsed attributes: %s", json.dumps(attributes))
    links = parse_protobuf_links(span.links, logger)
    events = parse_protobuf_events(span.events, logger)

    return Span(
        trace_id=trace_id,
        span_id=span_id,
        name=span.name,
        context={
            SpanContextFieldName.TRACE_ID: trace_id,
            SpanContextFieldName.SPAN_ID: span_id,
            SpanContextFieldName.TRACE_STATE: span.trace_state,
        },
        kind=span.kind,
        parent_id=parent_id if parent_id else None,
        start_time=convert_time_unix_nano_to_timestamp(span.start_time_unix_nano),
        end_time=convert_time_unix_nano_to_timestamp(span.end_time_unix_nano),
        status={
            SpanStatusFieldName.STATUS_CODE: _parse_otel_span_status_code(span.status.code),
            SpanStatusFieldName.DESCRIPTION: span.status.message,
        },
        attributes=attributes,
        links=links,
        events=events,
        resource=resource,
    )
