# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import PurePath

from flask import Blueprint, Flask, current_app, g, jsonify, redirect, request, url_for
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from promptflow._sdk._constants import PF_SERVICE_DEBUG, CreatedByFieldName
from promptflow._sdk._errors import MissingAzurePackage
from promptflow._sdk._service import Api
from promptflow._sdk._service.apis.collector import trace_collector
from promptflow._sdk._service.apis.connection import api as connection_api
from promptflow._sdk._service.apis.experiment import api as experiment_api
from promptflow._sdk._service.apis.flow import api as flow_api
from promptflow._sdk._service.apis.line_run import api as line_run_api
from promptflow._sdk._service.apis.run import api as run_api
from promptflow._sdk._service.apis.span import api as span_api
from promptflow._sdk._service.apis.telemetry import api as telemetry_api
from promptflow._sdk._service.apis.ui import api as ui_api
from promptflow._sdk._service.apis.ui import serve_chat_ui, serve_trace_ui
from promptflow._sdk._service.utils.utils import FormattedException, get_log_file_location, get_pfs_version
from promptflow._sdk._utilities.general_utils import overwrite_null_std_logger

overwrite_null_std_logger()


def heartbeat():
    response = {"promptflow": get_pfs_version()}
    return jsonify(response)


def root():
    return redirect(url_for("serve_trace_ui"))


def create_app():
    app = Flask(__name__)

    # in normal case, we don't need to handle CORS for PFS
    # as far as we know, local UX development might need to handle this
    # as there might be different ports in that scenario
    CORS(app)

    app.add_url_rule("/", view_func=root)
    app.add_url_rule("/heartbeat", view_func=heartbeat)
    app.add_url_rule(
        "/v1/traces", view_func=lambda: trace_collector(get_created_by_info_with_cache, app.logger), methods=["POST"]
    )
    app.add_url_rule("/v1.0/ui/traces/", defaults={"path": ""}, view_func=serve_trace_ui, methods=["GET"])
    app.add_url_rule("/v1.0/ui/traces/<path:path>", view_func=serve_trace_ui, methods=["GET"])
    app.add_url_rule("/v1.0/ui/chat/", defaults={"path": ""}, view_func=serve_chat_ui, methods=["GET"])
    app.add_url_rule("/v1.0/ui/chat/<path:path>", view_func=serve_chat_ui, methods=["GET"])
    with app.app_context():
        api_v1 = Blueprint("Prompt Flow Service", __name__, url_prefix="/v1.0", template_folder="static")

        # Registers resources from namespace for current instance of api
        api = Api(api_v1, title="Prompt Flow Service", version="1.0")
        api.add_namespace(connection_api)
        api.add_namespace(run_api)
        api.add_namespace(telemetry_api)
        api.add_namespace(span_api)
        api.add_namespace(line_run_api)
        api.add_namespace(ui_api)
        api.add_namespace(flow_api)
        api.add_namespace(experiment_api)
        app.register_blueprint(api_v1)

        # Disable flask-restx set X-Fields in header. https://flask-restx.readthedocs.io/en/latest/mask.html#usage
        app.config["RESTX_MASK_SWAGGER"] = False

        # Enable log
        app.logger.setLevel(logging.INFO)
        log_file = get_log_file_location()
        # Create a rotating file handler with a max size of 1 MB and keeping up to 1 backup files
        handler = RotatingFileHandler(filename=log_file, maxBytes=1_000_000, backupCount=1)
        formatter = logging.Formatter("[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")
        handler.setFormatter(formatter)

        # Create a stream handler to output logs to the terminal
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        # Set app logger to the only one RotatingFileHandler to avoid duplicate logs
        app.logger.handlers = [handler]
        if os.environ.get(PF_SERVICE_DEBUG) == "true":
            # Set app logger to use both the rotating file handler and the stream handler in debug mode
            app.logger.handlers.append(stream_handler)

        # Prevent logs from being handled by the root logger
        app.logger.propagate = False

        # Basic error handler
        @api.errorhandler(Exception)
        def handle_exception(e):
            """When any error occurs on the server, return a formatted error message."""
            from dataclasses import asdict

            if isinstance(e, HTTPException):
                return asdict(FormattedException(e), dict_factory=lambda x: {k: v for (k, v) in x if v}), e.code
            app.logger.error(e, exc_info=True, stack_info=True)
            formatted_exception = FormattedException(e)

            def handle_path_object(obj):
                if isinstance(obj, PurePath):
                    return str(obj)
                elif isinstance(obj, dict):
                    return {k: handle_path_object(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [handle_path_object(v) for v in obj]
                else:
                    return obj

            return (
                handle_path_object(asdict(formatted_exception, dict_factory=lambda x: {k: v for (k, v) in x if v})),
                formatted_exception.status_code,
            )

        @app.before_request
        def log_before_request_info():
            g.start = time.perf_counter()
            if "/v1.0/Connections" in request.url:
                request_body = "Request body not recorded for Connections API"
            else:
                request_body = request.get_data()

            app.logger.info("Request coming in: %s", request.url)
            app.logger.debug(
                "Headers: %s, Body: %s",
                request.headers,
                request_body,
            )

        @app.after_request
        def log_after_request_info(response):
            duration_time = time.perf_counter() - g.start
            app.logger.info(
                "Request_url: %s, duration: %s, response code: %s", request.url, duration_time, response.status_code
            )
            return response

    return app, api


created_by_for_local_to_cloud_trace = {}
created_by_for_local_to_cloud_trace_lock = threading.Lock()


def get_created_by_info_with_cache():
    if len(created_by_for_local_to_cloud_trace) > 0:
        return created_by_for_local_to_cloud_trace
    with created_by_for_local_to_cloud_trace_lock:
        if len(created_by_for_local_to_cloud_trace) > 0:
            return created_by_for_local_to_cloud_trace
        try:
            # The total time of collecting info is about 3s.
            import jwt
            from azure.identity import AzureCliCredential

            from promptflow.azure._utils.general import get_arm_token

            token = get_arm_token(credential=AzureCliCredential())
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            created_by_for_local_to_cloud_trace.update(
                {
                    CreatedByFieldName.OBJECT_ID: decoded_token["oid"],
                    CreatedByFieldName.TENANT_ID: decoded_token["tid"],
                    # Use appid as fallback for service principal scenario.
                    CreatedByFieldName.NAME: decoded_token.get("name", decoded_token.get("appid", "")),
                }
            )
        except ImportError:
            raise MissingAzurePackage()
        except Exception as e:
            # This function is only target to be used in Flask app.
            current_app.logger.error(f"Failed to get created_by info, stop writing span. Exception: {e}")
            raise e  # Created_by info is critical for local trace, so we should stop writing span if failed to get it.
    return created_by_for_local_to_cloud_trace
