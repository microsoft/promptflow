# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import os

from flask import Flask, g, jsonify, request
from opentelemetry import baggage, context, trace
from opentelemetry.trace.span import INVALID_SPAN

from promptflow._utils.exception_utils import ErrorResponse
from promptflow.contracts.run_info import Status
from promptflow.core._serving.app_base import PromptflowServingAppBasic
from promptflow.core._serving.constants import FEEDBACK_TRACE_FIELD_NAME, FEEDBACK_TRACE_SPAN_NAME
from promptflow.core._serving.utils import (
    enable_monitoring,
    load_request_data,
    serialize_attribute_value,
    try_extract_trace_context,
)
from promptflow.core._version import __version__
from promptflow.exceptions import SystemErrorException
from promptflow.tracing._operation_context import OperationContext

from .flask_context_data_provider import FlaskContextDataProvider
from .flask_response_creator import FlaskResponseCreator
from .utils import handle_error_to_response, streaming_response_required


class PromptflowServingApp(Flask, PromptflowServingAppBasic):
    def init(self, **kwargs):
        with self.app_context():
            self.init_app(**kwargs)
            add_default_routes(self)
            # register blueprints
            blue_prints = self.extension.get_blueprints(self.flow_monitor)
            for blue_print in blue_prints:
                self.register_blueprint(blue_print)

    def get_context_data_provider(self):
        return FlaskContextDataProvider()

    def streaming_response_required(self):
        return streaming_response_required()


def add_default_routes(app: PromptflowServingApp):
    logger = app.logger

    @app.errorhandler(Exception)
    def handle_error(e):
        err_resp, resp_code = handle_error_to_response(e, logger)
        app.flow_monitor.handle_error(e, resp_code)
        return err_resp, resp_code

    @app.route("/score", methods=["POST"])
    @enable_monitoring
    def score():
        """process a flow request in the runtime."""
        raw_data = request.get_data()
        logger.debug(f"PromptFlow executor received data: {raw_data}")
        app.init_invoker_if_not_exist()
        if app.flow.inputs.keys().__len__() == 0:
            data = {}
            logger.info("Flow has no input, request data will be ignored.")
        else:
            logger.info("Start loading request data...")
            data = load_request_data(app.flow, raw_data, logger)
        # set context data
        g.data = data
        g.flow_id = app.flow.id or app.flow.name
        run_id = g.get("req_id", None)
        # TODO: refine this once we can directly set the input/output log level to DEBUG in flow_invoker.
        disable_data_logging = logger.level >= logging.INFO
        span = trace.get_current_span()
        if span == INVALID_SPAN:
            # no parent span, try to extract trace context from request
            ctx = try_extract_trace_context(logger, request.headers)
        else:
            ctx = None
        token = context.attach(ctx) if ctx else None
        req_id = g.get("req_id", None)
        try:
            if req_id:
                OperationContext.get_instance()._add_otel_attributes("request_id", req_id)
            flow_result = app.flow_invoker.invoke(
                data, run_id=run_id, disable_input_output_logging=disable_data_logging
            )  # noqa
            g.flow_result = flow_result
        finally:
            # detach trace context if exist
            if token:
                context.detach(token)

        # check flow result, if failed, return error response
        if flow_result.run_info.status != Status.Completed:
            if flow_result.run_info.error:
                err = ErrorResponse(flow_result.run_info.error)
                g.err_code = err.innermost_error_code
                return jsonify(err.to_simplified_dict()), err.response_code
            else:
                # in case of run failed but can't find any error, return 500
                exception = SystemErrorException("Flow execution failed without error message.")
                return jsonify(ErrorResponse.from_exception(exception).to_simplified_dict()), 500

        intermediate_output = flow_result.output or {}
        # remove evaluation only fields
        result_output = {k: v for k, v in intermediate_output.items() if k not in app.response_fields_to_remove}
        accept_mimetypes = {p for p, v in request.accept_mimetypes} if request.accept_mimetypes else None
        response_creator = FlaskResponseCreator(
            flow_run_result=result_output,
            accept_mimetypes=accept_mimetypes,
            response_original_value=flow_result.response_original_value,
        )
        g.streaming = response_creator.has_stream_field and response_creator.accept_event_stream
        app.flow_monitor.setup_streaming_monitor_if_needed(response_creator)
        return response_creator.create_response()

    @app.route("/swagger.json", methods=["GET"])
    def swagger():
        """Get the swagger object."""
        return jsonify(app.swagger)

    @app.route("/health", methods=["GET"])
    def health():
        """Check if the runtime is alive."""
        return {"status": "Healthy", "version": __version__}

    @app.route("/version", methods=["GET"])
    def version():
        """Check the runtime's version."""
        build_info = os.environ.get("BUILD_INFO", "")
        try:
            build_info_dict = json.loads(build_info)
            version = build_info_dict["build_number"]
        except Exception:
            version = __version__
        return {"status": "Healthy", "build_info": build_info, "version": version}

    @app.route("/feedback", methods=["POST"])
    def feedback():
        ctx = try_extract_trace_context(logger, request.headers)
        open_telemetry_tracer = trace.get_tracer_provider().get_tracer("promptflow")
        token = context.attach(ctx) if ctx else None
        try:
            with open_telemetry_tracer.start_as_current_span(FEEDBACK_TRACE_SPAN_NAME) as span:
                data = request.get_data(as_text=True)
                should_flatten = request.args.get("flatten", "false").lower() == "true"
                if should_flatten:
                    try:
                        # try flatten the data to avoid data too big issue (especially for app insights scenario)
                        data = json.loads(data)
                        for k in data:
                            span.set_attribute(k, serialize_attribute_value(data[k]))
                    except Exception as e:
                        logger.warning(f"Failed to flatten the feedback, fall back to non-flattern mode. Error: {e}.")
                        span.set_attribute(FEEDBACK_TRACE_FIELD_NAME, data)
                else:
                    span.set_attribute(FEEDBACK_TRACE_FIELD_NAME, data)
                # add baggage data if exist
                data = baggage.get_all()
                if data:
                    for k, v in data.items():
                        span.set_attribute(k, v)
        finally:
            if token:
                context.detach(token)
        return {"status": "Feedback received."}
