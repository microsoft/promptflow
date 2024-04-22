# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from contextvars import ContextVar

from promptflow.core._serving.monitor.context_data_provider import ContextDataProvider

REQUEST_CTX = "request_context"
_request_ctx_var: ContextVar[dict] = ContextVar(REQUEST_CTX, default=None)


class FastapiContextDataProvider(ContextDataProvider):
    """FastAPI context data provider."""

    def get_request_data(self):
        """Get context data for monitor."""
        return _request_ctx_var.get().get("input_data", None)

    def set_request_data(self, data):
        """Set context data for monitor."""
        _request_ctx_var.get().update("input_data", data)

    def get_request_start_time(self):
        """Get request start time."""
        return _request_ctx_var.get().get("start_time")

    def set_request_start_time(self, start_time):
        """Set request start time."""
        _request_ctx_var.get().update("start_time", start_time)

    def get_request_id(self):
        """Get request id."""
        return _request_ctx_var.get().get("req_id", None)

    def set_request_id(self, req_id):
        """Set request id."""
        _request_ctx_var.get().update("req_id", req_id)

    def get_client_request_id(self):
        """Get client request id."""
        return _request_ctx_var.get().get("client_req_id", None)

    def set_client_request_id(self, client_req_id):
        """Set client request id."""
        _request_ctx_var.get().update("client_req_id", client_req_id)

    def get_flow_id(self):
        """Get flow id."""
        return _request_ctx_var.get().get("flow_id", None)

    def set_flow_id(self, flow_id):
        """Set flow id."""
        _request_ctx_var.get().update("flow_id", flow_id)

    def get_flow_result(self):
        """Get flow result."""
        return _request_ctx_var.get().get("flow_result", None)

    def set_flow_result(self, flow_result):
        """Set flow result."""
        _request_ctx_var.get().update("flow_result", flow_result)

    def is_response_streaming(self):
        """Get streaming."""
        return _request_ctx_var.get().get("streaming", False)

    def set_response_streaming(self, streaming):
        """Set streaming."""
        _request_ctx_var.get().update("streaming", streaming)

    def get_exception_code(self):
        """Get flow execution exception code."""
        return _request_ctx_var.get().get("err_code", None)

    def set_exception_code(self, err_code):
        """Set flow execution exception code."""
        _request_ctx_var.get().update("err_code", err_code)
