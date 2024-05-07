# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time

from flask import Blueprint
from flask import current_app as app
from flask import g, request

from promptflow.core._serving.monitor.flow_monitor import FlowMonitor
from promptflow.core._serving.v1.utils import streaming_response_required


def is_monitoring_enabled() -> bool:
    enabled = False
    if request.endpoint in app.view_functions:
        view_func = app.view_functions[request.endpoint]
        enabled = hasattr(view_func, "_enable_monitoring")
    return enabled


def construct_monitor_blueprint(flow_monitor: FlowMonitor):
    """Construct monitor blueprint."""
    monitor_blueprint = Blueprint("monitor_blueprint", __name__)
    logger = flow_monitor.logger

    @monitor_blueprint.before_app_request
    def start_monitoring():
        if not is_monitoring_enabled():
            return
        g.start_time = time.time()
        g.streaming = streaming_response_required()
        # if both request_id and client_request_id are provided, each will respect their own value.
        # if either one is provided, the provided one will be used for both request_id and client_request_id.
        # in aml deployment, request_id is provided by aml, user can only customize client_request_id.
        # in non-aml deployment, user can customize both request_id and client_request_id.
        g.req_id = request.headers.get("x-request-id", None)
        g.client_req_id = request.headers.get("x-ms-client-request-id", g.req_id)
        g.req_id = g.req_id or g.client_req_id
        logger.info(f"Start monitoring new request, request_id: {g.req_id}, client_request_id: {g.client_req_id}")
        flow_monitor.start_monitoring()

    @monitor_blueprint.after_app_request
    def finish_monitoring(response):
        if not is_monitoring_enabled():
            return response
        req_id = g.get("req_id", None)
        client_req_id = g.get("client_req_id", req_id)
        flow_monitor.finish_monitoring(response.status_code)
        logger.info(f"Finish monitoring request, request_id: {req_id}, client_request_id: {client_req_id}.")
        return response

    return monitor_blueprint
