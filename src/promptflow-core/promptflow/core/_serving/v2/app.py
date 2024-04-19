# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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
        self.add_middleware(middleware.MonitorMiddleware, flow_monitor=self.flow_monitor)
        self.add_middleware(middleware.ExceptionHandlingMiddleware)
        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

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
