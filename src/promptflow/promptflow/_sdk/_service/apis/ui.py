# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Response, render_template, url_for

from promptflow._sdk._service import Namespace, Resource

api = Namespace("ui", description="UI")


@api.route("/traces")
class TraceUI(Resource):
    def get(self):
        return Response(
            render_template("index.html", url_for=url_for),
            mimetype="text/html",
        )
