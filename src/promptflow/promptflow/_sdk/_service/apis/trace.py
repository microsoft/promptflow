# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask_restx import fields

from promptflow._constants import TraceEvaluationsFieldName, TraceFieldName
from promptflow._sdk._service import Namespace, Resource

api = Namespace("traces", description="Trace Management")


# trace models, for strong type support in Swagger
evaluations_model = api.model(
    "Evaluations",
    {
        TraceEvaluationsFieldName.NAME: fields.String(required=True),
        TraceEvaluationsFieldName.VALUE: fields.String(required=True),
        TraceEvaluationsFieldName.LINE_RUN_ID: fields.String(required=True),
    },
)
trace_model = api.model(
    "Trace",
    {
        TraceFieldName.LINE_RUN_ID: fields.String(required=True),
        TraceFieldName.INPUTS: fields.Raw(required=True),
        TraceFieldName.OUTPUTS: fields.Raw(required=True),
        TraceFieldName.EVALUATIONS: fields.List(fields.Nested(evaluations_model)),
        TraceFieldName.START_TIME: fields.DateTime(dt_format="iso8601", required=True),
        TraceFieldName.END_TIME: fields.DateTime(dt_format="iso8601", required=True),
        TraceFieldName.STATUS: fields.String(required=True),
    },
)


@api.route("/list")
class Traces(Resource):
    @api.doc(description="List traces")
    @api.marshal_list_with(trace_model)
    @api.response(code=200, description="Traces")
    def get(self):
        # TODO: implement this when we have a trace schema
        ...
