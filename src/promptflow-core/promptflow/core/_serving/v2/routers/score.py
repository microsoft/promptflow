# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from opentelemetry import context, trace
from opentelemetry.trace.span import INVALID_SPAN

from promptflow._utils.exception_utils import ErrorResponse
from promptflow.contracts.run_info import Status
from promptflow.core._serving.utils import load_request_data, try_extract_trace_context
from promptflow.exceptions import SystemErrorException
from promptflow.tracing._operation_context import OperationContext

from ..fastapi_context_data_provider import _request_ctx_var
from ..fastapi_response_creator import FastapiResponseCreator


def get_score_router(logger):
    router = APIRouter()

    @router.post("/score")
    async def score(request: Request):
        logger.info(f"Type: {type(request.app)}, {hasattr(request.app, 'flow')}, {hasattr(request.app, 'extension')}")
        # return {"status": "ok"}
        app = request.app
        raw_data = await request.body()
        logger.debug(f"PromptFlow executor received data: {raw_data}")
        app.init_invoker_if_not_exist()
        if app.flow.inputs.keys().__len__() == 0:
            data = {}
            logger.info("Flow has no input, request data will be ignored.")
        else:
            logger.info("Start loading request data...")
            data = load_request_data(app.flow, raw_data, logger)
        # set context data
        _request_ctx_var.get()["data"] = data
        _request_ctx_var.get()["flow_id"] = app.flow.id or app.flow.name
        run_id = _request_ctx_var.get().get("req_id", None)
        # TODO: refine this once we can directly set the input/output log level to DEBUG in flow_invoker.
        disable_data_logging = logger.level >= logging.INFO
        span = trace.get_current_span()
        if span == INVALID_SPAN:
            # no parent span, try to extract trace context from request
            logger.info("No parent span found, try to extract trace context from request.")
            ctx = try_extract_trace_context(logger, request.headers)
        else:
            ctx = None
        token = context.attach(ctx) if ctx else None
        try:
            if run_id:
                OperationContext.get_instance()._add_otel_attributes("request_id", run_id)
            flow_result = await app.flow_invoker.invoke_async(
                data, run_id=run_id, disable_input_output_logging=disable_data_logging
            )
            # return flow_result
            _request_ctx_var.get()["flow_result"] = flow_result
        finally:
            # detach trace context if exist
            if token:
                context.detach(token)

        # check flow result, if failed, return error response
        if flow_result.run_info.status != Status.Completed:
            if flow_result.run_info.error:
                err = ErrorResponse(flow_result.run_info.error)
                _request_ctx_var.get()["err_code"] = err.innermost_error_code
                return JSONResponse(content=err.to_simplified_dict(), status_code=int(err.response_code.value))
            else:
                # in case of run failed but can't find any error, return 500
                exception = SystemErrorException("Flow execution failed without error message.")
                error_details = ErrorResponse.from_exception(exception).to_simplified_dict()
                return JSONResponse(content=error_details, status_code=500)

        intermediate_output = flow_result.output or {}
        # remove evaluation only fields
        result_output = {k: v for k, v in intermediate_output.items() if k not in app.response_fields_to_remove}
        accept_headers = request.headers.getlist("accept")
        accept_mimetypes = set()
        for ah in accept_headers:
            accept_mimetypes.update([x.strip() for x in ah.split(",") if ah.strip()])
        response_creator = FastapiResponseCreator(
            flow_run_result=result_output,
            accept_mimetypes=accept_mimetypes,
            response_original_value=flow_result.response_original_value,
        )
        _request_ctx_var.get()["streaming"] = response_creator.has_stream_field and response_creator.accept_event_stream
        app.flow_monitor.setup_streaming_monitor_if_needed(response_creator)
        return response_creator.create_response()

    return router
