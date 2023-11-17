# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from flask import Blueprint, Flask, jsonify
from flask_restx import Api
from werkzeug.exceptions import HTTPException

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, PF_SERVICE_LOG_FILE
from promptflow._sdk._service.apis.connection import api as connection_api
from promptflow._sdk._service.apis.run import api as run_api
from promptflow._sdk._utils import get_promptflow_sdk_version, read_write_by_user


def heartbeat():
    response = {"sdk_version": get_promptflow_sdk_version()}
    return jsonify(response)


def create_app():
    app = Flask(__name__)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    with app.app_context():
        api_v1 = Blueprint("Prompt Flow Service", __name__, url_prefix="/v1.0")

        # Registers resources from namespace for current instance of api
        api = Api(api_v1, title="Prompt Flow Service", version="1.0")
        api.add_namespace(connection_api)
        api.add_namespace(run_api)
        app.register_blueprint(api_v1)

        # Disable flask-restx set X-Fields in header. https://flask-restx.readthedocs.io/en/latest/mask.html#usage
        app.config["RESTX_MASK_SWAGGER"] = False

        # Enable log
        app.logger.setLevel(logging.INFO)
        log_file = HOME_PROMPT_FLOW_DIR / PF_SERVICE_LOG_FILE
        log_file.touch(mode=read_write_by_user(), exist_ok=True)
        handler = logging.FileHandler(filename=log_file)
        app.logger.addHandler(handler)

        # Basic error handler
        @app.errorhandler(Exception)
        def handle_exception(e):
            if isinstance(e, HTTPException):
                return e
            app.logger.error(e, exc_info=True, stack_info=True)
            return jsonify({"error_message": "Internal Server Error"}), 500

    return app, api
