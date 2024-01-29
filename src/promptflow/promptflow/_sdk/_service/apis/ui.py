# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json

from flask import Response, render_template

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("ui", description="UI")

trace_parser = api.parser()
trace_parser.add_argument("session", type=str, required=True)
trace_parser.add_argument("parent_id", type=str, required=False)


@api.route("/traces")
class Trace(Resource):
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = trace_parser.parse_args()
        session_id = args.session
        parent_span_id = args.parent_id
        print(session_id, parent_span_id)
        traces = client._traces.list(
            session_id=session_id,
            parent_span_id=parent_span_id,
        )

        traces_json = json.dumps([trace._content for trace in traces])
        return Response(render_template("ui_traces.html", traces_json=traces_json), mimetype="text/html")
