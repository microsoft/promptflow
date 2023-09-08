# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import logging
import mimetypes
import os
from pathlib import Path

import flask
from flask import Flask, jsonify, request, url_for
from jinja2 import Template

from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._serving.response_creator import ResponseCreator
from promptflow._sdk._serving.utils import (
    get_output_fields_to_remove,
    get_sample_json,
    handle_error_to_response,
    load_request_data,
    streaming_response_required,
    validate_request_data,
)
from promptflow._sdk._utils import (
    resolve_connections_environment_variable_reference,
    setup_user_agent_to_operation_context,
    update_environment_variables_with_connections,
)
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.operations._run_submitter import variant_overwrite_context
from promptflow._version import VERSION
from promptflow.executor.flow_executor import FlowExecutor

from .swagger import generate_swagger

logger = logging.getLogger(LOGGER_NAME)
DEFAULT_STATIC_PATH = Path(__file__).parent / "static"
USER_AGENT = f"promptflow-local-serving/{VERSION}"


class PromptflowServingApp(Flask):
    def init(self, **kwargs):
        with self.app_context():
            self.executor: FlowExecutor = None
            # parse promptflow project path
            self.project_path = os.getenv("PROMPTFLOW_PROJECT_PATH", ".")
            logger.info(f"Project path: {self.project_path}")
            self.flow_entity = load_flow(self.project_path)
            static_folder = kwargs.get("static_folder", None)
            self.static_folder = static_folder if static_folder else DEFAULT_STATIC_PATH
            logger.info(f"Static_folder: {self.static_folder}")
            self.environment_variables = kwargs.get("environment_variables", {})
            os.environ.update(self.environment_variables)
            logger.info(f"Environment variable keys: {self.environment_variables.keys()}")
            self.sample = get_sample_json(self.project_path, logger)
            self.init_swagger()
            # ensure response has the correct content type
            mimetypes.add_type("application/javascript", ".js")
            mimetypes.add_type("text/css", ".css")
            setup_user_agent_to_operation_context(USER_AGENT)

    def init_executor_if_not_exist(self):
        if self.executor:
            return
        logger.info("Promptflow executor starts initializing...")
        # try get the connections
        logger.info("Promptflow serving app start getting connections from local...")
        connections = Flow._get_local_connections(executable=self.flow_entity._init_executable())
        resolve_connections_environment_variable_reference(connections)
        update_environment_variables_with_connections(connections)
        logger.info(f"Promptflow serving app get connections successfully. keys: {connections.keys()}")
        with variant_overwrite_context(self.flow_entity.code, None, None) as flow:
            self.executor = FlowExecutor.create(
                flow_file=flow.path, working_dir=flow.code, connections=connections, raise_ex=True
            )
        self.flow = self.executor._flow
        # Set the flow name as folder name
        self.flow.name = Path(self.project_path).stem
        self.response_fields_to_remove = get_output_fields_to_remove(self.flow, logger)
        self.executor.enable_streaming_for_llm_flow(streaming_response_required)
        logger.info("Promptflow executor initiated successfully.")

    def init_swagger(self):
        flow = self.flow_entity._init_executable()
        # Set the flow name as folder name
        flow.name = Path(self.project_path).stem
        self.response_fields_to_remove = get_output_fields_to_remove(flow, logger)
        self.swagger = generate_swagger(flow, self.sample, self.response_fields_to_remove)


app = PromptflowServingApp(__name__)
# CORS(app)


if __name__ != "__main__":
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)


@app.errorhandler(Exception)
def handle_error(e):
    return handle_error_to_response(e, logger)


@app.route("/score", methods=["POST"])
def score():
    """process a flow request in the runtime."""
    raw_data = request.get_data()
    logger.info(f"PromptFlow executor received data: {raw_data}")
    app.init_executor_if_not_exist()
    if app.flow.inputs.keys().__len__() == 0:
        data = {}
        logger.info(f"Flow has no input, request data '{raw_data}' will be ignored.")
    else:
        logger.info(f"Start loading request data '{raw_data}'.")
        data = load_request_data(app.flow, raw_data, logger)

    logger.info(f"Validating flow input with data {data!r}")
    validate_request_data(app.flow, data)
    logger.info(f"Execute flow with data {data!r}")
    result = app.executor.exec_line(data, allow_generator_output=streaming_response_required())
    # remove evaluation only fields
    result = {k: v for k, v in result.output.items() if k not in app.response_fields_to_remove}

    response_creator = ResponseCreator(
        flow_run_result=result,
        accept_mimetypes=request.accept_mimetypes,
    )
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


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def home(path):
    """Show the home page."""
    rules = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
    if request.path not in rules or request.method not in rules[request.path]:
        unsupported_message = (
            f"The requested api {request.path!r} with {request.method} is not supported by current app, "
            f"if you entered the URL manually please check your spelling and try again."
        )
        return unsupported_message, 404
    index_path = Path(app.static_folder) / "index.html"
    if index_path.exists():
        template = Template(open(index_path, "r", encoding="UTF-8").read())
        return flask.render_template(template, url_for=url_for)
    else:
        return "<h1>Welcome to promptflow app.</h1>"


def create_app(**kwargs):
    app.init(**kwargs)
    return app


if __name__ == "__main__":
    create_app().run()
