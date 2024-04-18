# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import g

from promptflow.core._serving.monitor.context_data_provider import ContextDataProvider


class FlaskContextDataProvider(ContextDataProvider):
    """Flask context data provider."""

    def get_request_data(self):
        """Get context data for monitor."""
        return g.get("data", None)

    def get_request_start_time(self):
        """Get request start time."""
        return g.get("start_time")

    def get_request_id(self):
        """Get request id."""
        return g.get("req_id", None)

    def get_client_request_id(self):
        """Get client request id."""
        return g.get("client_req_id", None)

    def get_flow_id(self):
        """Get flow id."""
        return g.get("flow_id", None)

    def get_flow_result(self):
        """Get flow result."""
        return g.get("flow_result", None)

    def is_response_streaming(self):
        """Get streaming."""
        return g.get("streaming", False)

    def get_exception_code(self):
        """Get flow execution exception code."""
        return g.get("err_code", None)
