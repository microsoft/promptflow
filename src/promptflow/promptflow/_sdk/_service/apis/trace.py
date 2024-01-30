# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask_restx import fields

from promptflow._constants import TraceAttributes
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("traces", description="Trace Management")

context_model = api.model(
    "Context",
    {
        "trace_id": fields.String(required=True),
        "span_id": fields.String(required=True),
        "trace_state": fields.String(required=True),
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
        TraceAttributes.FRAMEWORK: fields.String(required=True, default="promptflow"),
        TraceAttributes.SPAN_TYPE: fields.String(required=True, default="Function"),
        TraceAttributes.FUNCTION: fields.String(required=True),
        TraceAttributes.INPUTS: fields.String(required=True),
        TraceAttributes.OUTPUT: fields.String(required=True),
        TraceAttributes.SESSION_ID: fields.String(required=True),
        TraceAttributes.PATH: fields.String,
        TraceAttributes.FLOW_ID: fields.String,
        TraceAttributes.RUN: fields.String,
        TraceAttributes.EXPERIMENT: fields.String,
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
        "name": fields.String(required=True),
        "context": fields.Nested(context_model, required=True),
        "kind": fields.String(required=True),
        "parent_id": fields.String,
        "start_time": fields.DateTime(dt_format="iso8601"),
        "end_time": fields.DateTime(dt_format="iso8601"),
        "status": fields.Nested(status_model),
        "attributes": fields.Nested(attributes_model, required=True),
        "events": fields.List(fields.String),
        "links": fields.List(fields.String),
        "resource": fields.Nested(resource_model, required=True),
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
        traces = client._traces.list()
        return [trace._content for trace in traces]
