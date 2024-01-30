# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask_restx import fields

from promptflow._constants import TraceAttributeFieldName, TraceContextFieldName, TraceFieldName
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("traces", description="Trace Management")

# parsers for query parameters
trace_parser = api.parser()
trace_parser.add_argument("session", type=str, required=False)
trace_parser.add_argument("parent_id", type=str, required=False)

# trace models, for strong type support
context_model = api.model(
    "Context",
    {
        TraceContextFieldName.TRACE_ID: fields.String(required=True),
        TraceContextFieldName.SPAN_ID: fields.String(required=True),
        TraceContextFieldName.TRACE_STATE: fields.String(required=True),
    },
)
status_model = api.model(
    "StatusCode",
    {
        "status_code": fields.String(required=True),
    },
)
attributes_model = api.model(
    "Attributes",
    {
        TraceAttributeFieldName.FRAMEWORK: fields.String(required=True, default="promptflow"),
        TraceAttributeFieldName.SPAN_TYPE: fields.String(required=True, default="Function"),
        TraceAttributeFieldName.FUNCTION: fields.String(required=True),
        TraceAttributeFieldName.INPUTS: fields.String(required=True),
        TraceAttributeFieldName.OUTPUT: fields.String(required=True),
        TraceAttributeFieldName.SESSION_ID: fields.String(required=True),
        TraceAttributeFieldName.PATH: fields.String,
        TraceAttributeFieldName.FLOW_ID: fields.String,
        TraceAttributeFieldName.RUN: fields.String,
        TraceAttributeFieldName.EXPERIMENT: fields.String,
    },
)
resource_attributes_model = api.model(
    "ResourceAttributes",
    {
        "service.name": fields.String(default="promptflow"),
    },
)
resource_model = api.model(
    "Resource",
    {
        "attributes": fields.Nested(resource_attributes_model, required=True),
        "schema_url": fields.String,
    },
)
trace_model = api.model(
    "Trace",
    {
        TraceFieldName.NAME: fields.String(required=True),
        TraceFieldName.CONTEXT: fields.Nested(context_model, required=True),
        TraceFieldName.KIND: fields.String(required=True),
        TraceFieldName.PARENT_ID: fields.String,
        TraceFieldName.START_TIME: fields.DateTime(dt_format="iso8601"),
        TraceFieldName.END_TIME: fields.DateTime(dt_format="iso8601"),
        TraceFieldName.STATUS: fields.Nested(status_model),
        TraceFieldName.ATTRIBUTES: fields.Nested(attributes_model, required=True),
        TraceFieldName.EVENTS: fields.List(fields.String),
        TraceFieldName.LINKS: fields.List(fields.String),
        TraceFieldName.RESOURCE: fields.Nested(resource_model, required=True),
    },
)


@api.route("/list")
class TraceList(Resource):
    @api.doc(description="List all traces")
    @api.marshal_list_with(trace_model)
    @api.response(code=200, description="Traces")
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = trace_parser.parse_args()
        session_id = args.session
        parent_span_id = args.parent_id
        traces = client._traces.list(
            session_id=session_id,
            parent_span_id=parent_span_id,
        )
        return [trace._content for trace in traces]
