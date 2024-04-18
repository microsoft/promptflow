# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter
from promptflow.core._serving._errors import NotAcceptable

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
        streaming = False
        for a in accept:
            if "text/event-stream" in a:
                streaming = True
                break
        ctx_data["streaming"] = streaming
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


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            resp_data, response_code = error_to_response(exc, request.app.logger)
            request.app.flow_monitor.handle_error(exc, response_code)
            return JSONResponse(resp_data, response_code)


def error_to_response(e, logger):
    presenter = ExceptionPresenter.create(e)
    logger.error(f"Promptflow serving app error: {presenter.to_dict()}")
    logger.error(f"Promptflow serving error traceback: {presenter.formatted_traceback}")
    resp = ErrorResponse(presenter.to_dict())
    response_code = int(resp.response_code.value)
    # The http response code for NotAcceptable is 406.
    # Currently the error framework does not allow response code overriding,
    # we add a check here to override the response code.
    # TODO: Consider how to embed this logic into the error framework.
    if isinstance(e, NotAcceptable):
        response_code = 406
    return resp.to_simplified_dict(), response_code
