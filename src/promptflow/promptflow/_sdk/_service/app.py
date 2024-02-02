# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from logging.handlers import RotatingFileHandler

from flask import Blueprint, Flask, jsonify
from werkzeug.exceptions import HTTPException

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, PF_SERVICE_LOG_FILE
from promptflow._sdk._service import Api
from promptflow._sdk._service.apis.collector import trace_collector
from promptflow._sdk._service.apis.connection import api as connection_api
from promptflow._sdk._service.apis.run import api as run_api
from promptflow._sdk._service.apis.span import api as span_api
from promptflow._sdk._service.apis.telemetry import api as telemetry_api
from promptflow._sdk._service.apis.ui import api as ui_api
from promptflow._sdk._service.utils.utils import FormattedException
from promptflow._sdk._utils import get_promptflow_sdk_version, read_write_by_user


def heartbeat():
    response = {"promptflow": get_promptflow_sdk_version()}
    return jsonify(response)


def create_app():
    app = Flask(__name__)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    app.add_url_rule("/v1/traces", view_func=trace_collector, methods=["POST"])
    with app.app_context():
        api_v1 = Blueprint("Prompt Flow Service", __name__, url_prefix="/v1.0")

        # Registers resources from namespace for current instance of api
        api = Api(api_v1, title="Prompt Flow Service", version="1.0")
        api.add_namespace(connection_api)
        api.add_namespace(run_api)
        api.add_namespace(telemetry_api)
        api.add_namespace(span_api)
        api.add_namespace(ui_api)
        app.register_blueprint(api_v1)

        # Disable flask-restx set X-Fields in header. https://flask-restx.readthedocs.io/en/latest/mask.html#usage
        app.config["RESTX_MASK_SWAGGER"] = False

        # Enable log
        app.logger.setLevel(logging.INFO)
        log_file = HOME_PROMPT_FLOW_DIR / PF_SERVICE_LOG_FILE
        log_file.touch(mode=read_write_by_user(), exist_ok=True)
        # Create a rotating file handler with a max size of 1 MB and keeping up to 1 backup files
        handler = RotatingFileHandler(filename=log_file, maxBytes=1_000_000, backupCount=1)
        formatter = logging.Formatter("[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

        # Basic error handler
        @api.errorhandler(Exception)
        def handle_exception(e):
            """When any error occurs on the server, return a formatted error message."""
            from dataclasses import asdict

            if isinstance(e, HTTPException):
                return asdict(FormattedException(e), dict_factory=lambda x: {k: v for (k, v) in x if v}), e.code
            app.logger.error(e, exc_info=True, stack_info=True)
            formatted_exception = FormattedException(e)
            return (
                asdict(formatted_exception, dict_factory=lambda x: {k: v for (k, v) in x if v}),
                formatted_exception.status_code,
            )

    return app, api
