# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask, jsonify

from promptflow._sdk._service.run import run_bp
from promptflow._sdk._utils import get_promptflow_sdk_version


def heartbeat():
    response = {"sdk_version": get_promptflow_sdk_version()}
    return jsonify(response)


def create_app():
    app = Flask(__name__)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    app.register_blueprint(run_bp)
    return app
