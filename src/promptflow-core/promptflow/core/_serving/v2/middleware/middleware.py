import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

from ..fastapi_context_data_provider import _request_ctx_var

routes_with_middleware = ["/score"]


class MonitorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, flow_monitor):
        super().__init__(app)
        self.flow_monitor = flow_monitor
        self.logger = self.flow_monitor.logger

    async def dispatch(self, request: Request, call_next):
        # check whether to enable monitoring
        if request.url.path not in routes_with_middleware:
            return await call_next(request)
        # prepare monitoring context data
        ctx_data = {}
        ctx_data["start_time"] = time.time()
        # if both request_id and client_request_id are provided, each will respect their own value.
        # if either one is provided, the provided one will be used for both request_id and client_request_id.
        # in aml deployment, request_id is provided by aml, user can only customize client_request_id.
        # in non-aml deployment, user can customize both request_id and client_request_id.
        req_id = request.headers.get("x-request-id")
        client_req_id = request.headers.get("x-ms-client-request-id", req_id)
        req_id = req_id if req_id else client_req_id
        ctx_data["req_id"] = req_id
        ctx_data["client_req_id"] = client_req_id
        accept = request.headers.getlist("Accept")
        ctx_data["streaming"] = "text/event-stream" in accept
        token = _request_ctx_var.set(ctx_data)
        self.flow_monitor.start_monitoring()
        self.logger.info(f"Start monitoring new request, request_id: {req_id}, client_request_id: {client_req_id}")

        try:
            # process the request and get the response
            response = await call_next(request)
            # finish request monitoring
            self.flow_monitor.finish_monitoring(response.status_code)
            self.logger.info(f"Finish monitoring request, request_id: {req_id}, client_request_id: {client_req_id}.")
            return response
        finally:
            # self.logger.debug(f"context data: {_request_ctx_var.get()}")
            _request_ctx_var.reset(token)
