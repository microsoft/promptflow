# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import dataclass

from flask_restx import fields

from promptflow._constants import (
    SpanContextFieldName,
    SpanEventFieldName,
    SpanFieldName,
    SpanLinkFieldName,
    SpanResourceFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import PFS_MODEL_DATETIME_FORMAT
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow.client import PFClient

api = Namespace("Spans", description="Spans Management")

# parsers for query parameters
list_span_parser = api.parser()
list_span_parser.add_argument("trace_ids", type=str, required=False)
list_span_parser.add_argument("lazy_load", type=str, required=False)


# use @dataclass for strong type
@dataclass
class ListSpanParser:
    trace_ids: typing.List[str]
    lazy_load: bool

    @staticmethod
    def from_request() -> "ListSpanParser":
        args = list_span_parser.parse_args()
        return ListSpanParser(
            trace_ids=args.trace_ids.split(",") if args.trace_ids is not None else args.trace_ids,
            lazy_load=False if str(args.lazy_load).lower() == "false" else True,
        )


# span models, for strong type support in Swagger
context_model = api.model(
    "Context",
    {
        SpanContextFieldName.TRACE_ID: fields.String(required=True),
        SpanContextFieldName.SPAN_ID: fields.String(required=True),
        SpanContextFieldName.TRACE_STATE: fields.String(required=True),
    },
)
status_model = api.model(
    "Status",
    {
        SpanStatusFieldName.STATUS_CODE: fields.String(required=True),
        SpanStatusFieldName.DESCRIPTION: fields.String,
    },
)
resource_model = api.model(
    "Resource",
    {
        SpanResourceFieldName.ATTRIBUTES: fields.Raw(required=True),
        SpanResourceFieldName.SCHEMA_URL: fields.String,
    },
)
event_model = api.model(
    "Event",
    {
        SpanEventFieldName.NAME: fields.String(required=True),
        SpanEventFieldName.TIMESTAMP: fields.DateTime(dt_format=PFS_MODEL_DATETIME_FORMAT),
        SpanEventFieldName.ATTRIBUTES: fields.Raw,
    },
)
link_model = api.model(
    "Link",
    {
        SpanLinkFieldName.CONTEXT: fields.Nested(context_model),
        SpanLinkFieldName.ATTRIBUTES: fields.Raw,
    },
)
span_model = api.model(
    "Span",
    {
        # marshmallow fields cannot parse field name with dot (e.g., referenced.line_run_id)
        # so for `attributes` and `resource.attributes`, not support strong type with raw dict
        SpanFieldName.NAME: fields.String(required=True),
        SpanFieldName.CONTEXT: fields.Nested(context_model, required=True, skip_none=True),
        SpanFieldName.KIND: fields.String(required=True),
        SpanFieldName.PARENT_ID: fields.String,
        SpanFieldName.START_TIME: fields.DateTime(dt_format=PFS_MODEL_DATETIME_FORMAT),
        SpanFieldName.END_TIME: fields.DateTime(dt_format=PFS_MODEL_DATETIME_FORMAT),
        SpanFieldName.STATUS: fields.Nested(status_model, skip_none=True),
        SpanFieldName.ATTRIBUTES: fields.Raw(required=True),
        SpanFieldName.EVENTS: fields.List(fields.Nested(event_model)),
        SpanFieldName.LINKS: fields.List(fields.Nested(link_model)),
        SpanFieldName.RESOURCE: fields.Nested(resource_model, required=True, skip_none=True),
        SpanFieldName.EXTERNAL_EVENT_DATA_URIS: fields.List(fields.String),
    },
)


@api.route("/list")
class Spans(Resource):
    @api.doc(description="List spans")
    @api.marshal_list_with(span_model)
    @api.response(code=200, description="Spans")
    def get(self):
        client: PFClient = get_client_from_request()
        args = ListSpanParser.from_request()
        spans = client.traces.list_spans(
            trace_ids=args.trace_ids,
            lazy_load=args.lazy_load,
        )
        return [span._to_rest_object() for span in spans]


@api.route("/Event/<string:event_id>")
class Event(Resource):
    @api.doc(description="Get span event with event id")
    @api.response(code=200, description="Event")
    def get(self, event_id: str):
        client: PFClient = get_client_from_request()
        return client.traces.get_event(event_id=event_id)
