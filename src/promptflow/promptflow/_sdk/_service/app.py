# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask, jsonify, Blueprint
from flask_restx import Api

from promptflow._sdk._service.apis.connection import api as connection_api
from promptflow._sdk._service.apis.run import api as run_api
from promptflow._sdk._utils import get_promptflow_sdk_version


def heartbeat():
    response = {"sdk_version": get_promptflow_sdk_version()}
    return jsonify(response)


def create_app():
    app = Flask(__name__)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    with app.app_context():
        api_v1 = Blueprint("Prompt Flow Service", __name__, url_prefix="/v1.0")
        api = Api(api_v1, title="Prompt Flow Service", version='1.0')
        api.add_namespace(connection_api)
        api.add_namespace(run_api)

        app.register_blueprint(api_v1)
    return app, api
