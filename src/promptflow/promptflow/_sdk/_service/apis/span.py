# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import dataclass

from flask_restx import fields

from promptflow._constants import (
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
    SpanStatusFieldName,
)
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
attributes_model = api.model(
    "Attributes",
    {
        SpanAttributeFieldName.FRAMEWORK: fields.String(required=True, default="promptflow"),
        SpanAttributeFieldName.SPAN_TYPE: fields.String(required=True, default="Function"),
        SpanAttributeFieldName.FUNCTION: fields.String(required=True),
        SpanAttributeFieldName.INPUTS: fields.String(required=True),
        SpanAttributeFieldName.OUTPUT: fields.String,
        # token metrics
        SpanAttributeFieldName.COMPLETION_TOKEN_COUNT: fields.String,
        SpanAttributeFieldName.PROMPT_TOKEN_COUNT: fields.String,
        SpanAttributeFieldName.TOTAL_TOKEN_COUNT: fields.String,
        SpanAttributeFieldName.CUMULATIVE_COMPLETION_TOKEN_COUNT: fields.String,
        SpanAttributeFieldName.CUMULATIVE_PROMPT_TOKEN_COUNT: fields.String,
        SpanAttributeFieldName.CUMULATIVE_TOTAL_TOKEN_COUNT: fields.String,
        # test
        SpanAttributeFieldName.REFERENCED_LINE_RUN_ID: fields.String,
        # batch run
        SpanAttributeFieldName.BATCH_RUN_ID: fields.String,
        SpanAttributeFieldName.LINE_NUMBER: fields.String,
        SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID: fields.String,
    },
)
resource_attributes_model = api.model(
    "ResourceAttributes",
    {
        SpanResourceAttributesFieldName.SERVICE_NAME: fields.String(required=True, default="promptflow"),
        SpanResourceAttributesFieldName.SESSION_ID: fields.String(required=True),
        SpanResourceAttributesFieldName.EXPERIMENT_NAME: fields.String,
    },
)
resource_model = api.model(
    "Resource",
    {
        SpanResourceFieldName.ATTRIBUTES: fields.Nested(resource_attributes_model, required=True),
        SpanResourceFieldName.SCHEMA_URL: fields.String,
    },
)
span_model = api.model(
    "Span",
    {
        SpanFieldName.NAME: fields.String(required=True),
        SpanFieldName.CONTEXT: fields.Nested(context_model, required=True),
        SpanFieldName.KIND: fields.String(required=True),
        SpanFieldName.PARENT_ID: fields.String,
        SpanFieldName.START_TIME: fields.DateTime(dt_format=PFS_MODEL_DATETIME_FORMAT),
        SpanFieldName.END_TIME: fields.DateTime(dt_format=PFS_MODEL_DATETIME_FORMAT),
        SpanFieldName.STATUS: fields.Nested(status_model),
        SpanFieldName.ATTRIBUTES: fields.Nested(attributes_model, required=True),
        SpanFieldName.EVENTS: fields.List(fields.String),
        SpanFieldName.LINKS: fields.List(fields.String),
        SpanFieldName.RESOURCE: fields.Nested(resource_model, required=True),
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
