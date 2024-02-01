# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._sdk._service import Namespace, Resource

api = Namespace("traces", description="Trace Management")


@api.route("/list")
class Traces(Resource):
    @api.doc(description="List traces")
    @api.response(code=200, description="Traces")
    def get(self):
        # TODO: implement this when we have a trace schema
        ...
