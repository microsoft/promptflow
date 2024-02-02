# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Blueprint, current_app as app, request
from promptflow._sdk._serving.monitor.flow_monitor import FlowMonitor


def is_monitoring_enabled() -> bool:
    enabled = False
    if request.endpoint in app.view_functions:
        view_func = app.view_functions[request.endpoint]
        enabled = hasattr(view_func, "_enable_monitoring")
    return enabled


def construct_monitor_blueprint(flow_monitor: FlowMonitor):
    """Construct monitor blueprint."""
    monitor_blueprint = Blueprint("monitor_blueprint", __name__)

    @monitor_blueprint.before_app_request
    def start_monitoring():
        if not is_monitoring_enabled():
            return
        flow_monitor.start_monitoring()

    @monitor_blueprint.after_app_request
    def finish_monitoring(response):
        # add request id in response header.
        req_id = request.headers.get("x-request-id", None)
        if req_id:
            response.headers["x-request-id"] = req_id
        client_req_id = request.headers.get("x-ms-client-request-id", req_id)
        if client_req_id:
            response.headers["x-ms-client-request-id"] = client_req_id
        if not is_monitoring_enabled():
            return response
        flow_monitor.finish_monitoring(response.status_code)
        return response

    return monitor_blueprint
