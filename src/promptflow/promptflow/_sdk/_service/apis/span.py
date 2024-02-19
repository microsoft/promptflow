# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import dataclass

from flask_restx import fields

from promptflow._constants import SpanContextFieldName, SpanFieldName, SpanResourceFieldName, SpanStatusFieldName
from promptflow._sdk._constants import PFS_MODEL_DATETIME_FORMAT
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("Spans", description="Spans Management")

# parsers for query parameters
list_span_parser = api.parser()
list_span_parser.add_argument("session", type=str, required=False)


# use @dataclass for strong type
@dataclass
class ListSpanParser:
    session_id: typing.Optional[str] = None

    @staticmethod
    def from_request() -> "ListSpanParser":
        args = list_span_parser.parse_args()
        return ListSpanParser(
            session_id=args.session,
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
    },
)
resource_model = api.model(
    "Resource",
    {
        SpanResourceFieldName.ATTRIBUTES: fields.Raw(required=True),
        SpanResourceFieldName.SCHEMA_URL: fields.String,
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
        SpanFieldName.EVENTS: fields.List(fields.String),
        SpanFieldName.LINKS: fields.List(fields.String),
        SpanFieldName.RESOURCE: fields.Nested(resource_model, required=True, skip_none=True),
    },
)


@api.route("/list")
class Spans(Resource):
    @api.doc(description="List spans")
    @api.marshal_list_with(span_model)
    @api.response(code=200, description="Spans")
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = ListSpanParser.from_request()
        spans = client._traces.list_spans(
            session_id=args.session_id,
        )
        return [span._content for span in spans]
