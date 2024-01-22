# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Dict

from flask import Flask, g, jsonify, request

from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._serving.extension.extension_factory import ExtensionFactory
from promptflow._sdk._serving.flow_invoker import FlowInvoker
from promptflow._sdk._serving.response_creator import ResponseCreator
from promptflow._sdk._serving.utils import (
    enable_monitoring,
    get_output_fields_to_remove,
    get_sample_json,
    handle_error_to_response,
    load_request_data,
    streaming_response_required,
)
from promptflow._sdk._utils import setup_user_agent_to_operation_context
from promptflow._utils.exception_utils import ErrorResponse
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._version import VERSION
from promptflow.contracts.run_info import Status
from promptflow.exceptions import SystemErrorException
from promptflow.storage._run_storage import DummyRunStorage

from .swagger import generate_swagger

logger = LoggerFactory.get_logger("pfserving-app", target_stdout=True)
DEFAULT_STATIC_PATH = Path(__file__).parent / "static"
USER_AGENT = f"promptflow-local-serving/{VERSION}"


class PromptflowServingApp(Flask):
    def init(self, **kwargs):
        with self.app_context():
            # default to local, can be override when creating the app
            self.extension = ExtensionFactory.create_extension(logger, **kwargs)

            self.flow_invoker: FlowInvoker = None
            # parse promptflow project path
            self.project_path = self.extension.get_flow_project_path()
            logger.info(f"Project path: {self.project_path}")
            self.flow_entity = load_flow(self.project_path)
            self.flow = self.flow_entity._init_executable()

            # enable environment_variables
            environment_variables = kwargs.get("environment_variables", {})
            os.environ.update(environment_variables)
            default_environment_variables = self.flow.get_environment_variables_with_overrides()
            self.set_default_environment_variables(default_environment_variables)

            self.flow_name = self.extension.get_flow_name()
            self.flow.name = self.flow_name
            conn_data_override, conn_name_override = self.extension.get_override_connections(self.flow)
            self.connections_override = conn_data_override
            self.connections_name_override = conn_name_override

            self.flow_monitor = self.extension.get_flow_monitor()

            self.connection_provider = self.extension.get_connection_provider()
            self.credential = self.extension.get_credential()
            self.sample = get_sample_json(self.project_path, logger)
            self.init_swagger()
            # try to initialize the flow invoker
            try:
                self.init_invoker_if_not_exist()
            except Exception as e:
                if self.extension.raise_ex_on_invoker_initialization_failure(e):
                    raise e
            # ensure response has the correct content type
            mimetypes.add_type("application/javascript", ".js")
            mimetypes.add_type("text/css", ".css")
            setup_user_agent_to_operation_context(self.extension.get_user_agent())

            add_default_routes(self)
            # register blueprints
            blue_prints = self.extension.get_blueprints()
            for blue_print in blue_prints:
                self.register_blueprint(blue_print)

    def init_invoker_if_not_exist(self):
        if self.flow_invoker:
            return
        logger.info("Promptflow executor starts initializing...")
        self.flow_invoker = FlowInvoker(
            self.project_path,
            connection_provider=self.connection_provider,
            streaming=streaming_response_required,
            raise_ex=False,
            connections=self.connections_override,
            connections_name_overrides=self.connections_name_override,
            # for serving, we don't need to persist intermediate result, this is to avoid memory leak.
            storage=DummyRunStorage(),
            credential=self.credential,
        )
        self.flow = self.flow_invoker.flow
        # Set the flow name as folder name
        self.flow.name = self.flow_name
        self.response_fields_to_remove = get_output_fields_to_remove(self.flow, logger)
        logger.info("Promptflow executor initializing succeed!")

    def init_swagger(self):
        self.response_fields_to_remove = get_output_fields_to_remove(self.flow, logger)
        self.swagger = generate_swagger(self.flow, self.sample, self.response_fields_to_remove)

    def set_default_environment_variables(self, default_environment_variables: Dict[str, str] = None):
        if default_environment_variables is None:
            return
        for key, value in default_environment_variables.items():
            if key not in os.environ:
                os.environ[key] = value


def add_default_routes(app: PromptflowServingApp):
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
        flow_result = app.flow_invoker.invoke(data, run_id=run_id, disable_input_output_logging=disable_data_logging)
        g.flow_result = flow_result

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

        response_creator = ResponseCreator(
            flow_run_result=result_output,
            accept_mimetypes=request.accept_mimetypes,
        )
        app.flow_monitor.setup_streaming_monitor_if_needed(response_creator, data, intermediate_output)
        return response_creator.create_response()

    @app.route("/swagger.json", methods=["GET"])
    def swagger():
        """Get the swagger object."""
        return jsonify(app.swagger)

    @app.route("/health", methods=["GET"])
    def health():
        """Check if the runtime is alive."""
        return {"status": "Healthy", "version": VERSION}

    @app.route("/version", methods=["GET"])
    def version():
        """Check the runtime's version."""
        build_info = os.environ.get("BUILD_INFO", "")
        try:
            build_info_dict = json.loads(build_info)
            version = build_info_dict["build_number"]
        except Exception:
            version = VERSION
        return {"status": "Healthy", "build_info": build_info, "version": version}


def create_app(**kwargs):
    app = PromptflowServingApp(__name__)
    if __name__ != "__main__":
        app.logger.handlers = logger.handlers
        app.logger.setLevel(logger.level)
    app.init(**kwargs)
    return app


if __name__ == "__main__":
    create_app().run()
