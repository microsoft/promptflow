# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from flask import Response, render_template

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("ui", description="UI")

trace_parser = api.parser()
trace_parser.add_argument("session", type=str, required=True)


@api.route("/traces")
class Trace(Resource):
    def get(self):
        args = trace_parser.parse_args()
        session_id = args.session
        print(session_id)
        # get traces from database
        # TODO: query by `session_id`
        traces = get_client_from_request()._traces.list()

        data = []
        for trace in traces:
            data.append(
                {
                    "span_id": trace.id,
                    "trace_id": trace.trace_id,
                    "content": trace.content,
                }
            )
        return Response(render_template("ui_traces.j2", data=data), mimetype="text/html")
