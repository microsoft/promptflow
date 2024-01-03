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
        if not is_monitoring_enabled():
            return response
        flow_monitor.finish_monitoring(response.status_code)
        return response

    return monitor_blueprint
