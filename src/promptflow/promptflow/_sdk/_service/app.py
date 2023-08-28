# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask, Response

from promptflow._sdk._service.run import run_bp


def heartbeat():
    return Response(status=204)


def create_app():
    app = Flask(__name__)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    app.register_blueprint(run_bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
