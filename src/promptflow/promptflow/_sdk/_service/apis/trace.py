# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import jsonify

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("traces", description="Trace Management")


@api.route("/list")
class TraceList(Resource):
    @api.response(code=200, description="Traces")
    @api.doc(description="List all traces")
    def get(self):
        traces = get_client_from_request()._traces.list()
        traces_dict = [trace.content for trace in traces]
        return jsonify(traces_dict)
