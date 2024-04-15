# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter
from promptflow.core._serving._errors import NotAcceptable
from promptflow.core._serving.app_base import PromptflowServingAppBasic
from promptflow.core._serving.v2.middleware import middleware
from promptflow.core._serving.v2.routers import feedback, general, score, staticweb

from .fastapi_context_data_provider import FastapiContextDataProvider, _request_ctx_var


class PromptFlowServingAppV2(FastAPI, PromptflowServingAppBasic):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_app(**kwargs)
        static_folder = self.extension.static_folder if hasattr(self.extension, "static_folder") else None
        if static_folder:
            self.mount("/static", StaticFiles(directory=static_folder), name="static")
        self.include_router(score.get_score_router(self.logger))
        self.include_router(general.get_general_router(self.swagger))
        self.include_router(feedback.get_feedback_router(self.logger))
        self.include_router(staticweb.get_staticweb_router(self.logger, static_folder))
        self.add_exception_handler(404, not_found_exception_handler)
        self.add_exception_handler(Exception, default_exception_handler)
        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.add_middleware(middleware.MonitorMiddleware, flow_monitor=self.flow_monitor)

    def get_context_data_provider(self):
        return FastapiContextDataProvider()

    def streaming_response_required(self):
        return _request_ctx_var.get().get("streaming", False)


async def not_found_exception_handler(request: Request, exc: HTTPException):
    unsupported_message = (
        f"The requested api {request.url} with {request.method} is not supported by current app, "
        f"if you entered the URL manually please check your spelling and try again."
    )
    return HTMLResponse(unsupported_message, 404)


async def default_exception_handler(request: Request, exc: Exception):
    resp_data, response_code = error_to_response(exc, request.app.logger)
    request.app.flow_monitor.handle_error(exc, response_code)
    return JSONResponse(resp_data, response_code)


def error_to_response(e, logger):
    presenter = ExceptionPresenter.create(e)
    logger.error(f"Promptflow serving app error: {presenter.to_dict()}")
    logger.error(f"Promptflow serving error traceback: {presenter.formatted_traceback}")
    resp = ErrorResponse(presenter.to_dict())
    response_code = resp.response_code
    # The http response code for NotAcceptable is 406.
    # Currently the error framework does not allow response code overriding,
    # we add a check here to override the response code.
    # TODO: Consider how to embed this logic into the error framework.
    if isinstance(e, NotAcceptable):
        response_code = 406
    return resp.to_simplified_dict(), response_code
