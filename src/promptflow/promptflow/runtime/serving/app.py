# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import mimetypes
import os
from pathlib import Path

import flask
from flask import Flask, jsonify, request, url_for
from jinja2 import Template

from promptflow._constants import DEFAULT_FLOW_YAML_FILE, PromptflowEdition, RuntimeMode
from promptflow._version import VERSION
from promptflow.contracts.flow import Flow
from promptflow.core.operation_context import OperationContext
from promptflow.exceptions import ErrorTarget
from promptflow.executor import FlowExecutionCoodinator
from promptflow.executor.flow_executor import FlowExecutor
from promptflow.runtime import PromptFlowRuntime
from promptflow.runtime.utils import logger
from promptflow.runtime.utils._utils import decode_dict
from promptflow.sdk._serving.error_codes import FlowFileNotFound
from promptflow.sdk._serving.response_creator import ResponseCreator
from promptflow.sdk._serving.swagger import generate_swagger
from promptflow.sdk._serving.utils import (
    get_output_fields_to_remove,
    get_sample_json,
    handle_error_to_response,
    load_request_data,
    streaming_response_required,
    validate_request_data,
)
from promptflow.utils.utils import load_json

# from flask_cors import CORS


class PromptflowServingApp(Flask):
    def init(self, **kwargs):
        with self.app_context():
            self.logger.handlers = logger.handlers
            self.logger.setLevel(logger.level)
            self.executor: FlowExecutor = None
            # parse promptflow project path
            project_path: str = os.getenv("PROMPTFLOW_PROJECT_PATH", None)
            if not project_path:
                model_dir = os.getenv("AZUREML_MODEL_DIR", ".")
                model_rootdir = os.listdir(model_dir)[0]
                project_path = os.path.join(model_dir, model_rootdir)
            self.project_path = project_path
            self.logger.info(f"Model path: {project_path}")
            static_folder = kwargs.get("static_folder", None)
            self.static_folder = static_folder if static_folder else project_path
            self.logger.info(f"Static_folder: {self.static_folder}")
            # load swagger sample if exists
            self.sample = get_sample_json(self.project_path, logger)
            self.init_swagger()
            # check whether to enable MDC for model monitoring
            mdc_flag = os.getenv("PROMPTFLOW_MDC_ENABLE", "false")
            self.mdc_enabled = mdc_flag.lower() == "true"
            self.mdc_init_success = False
            if self.mdc_enabled:
                self.mdc_init_success = self.init_data_collector()
            self.logger.info(f"Mdc enabled: {self.mdc_enabled}, md init success: {self.mdc_init_success}")
            # ensure response has the correct content type
            mimetypes.add_type("application/javascript", ".js")
            mimetypes.add_type("text/css", ".css")

    def init_data_collector(self) -> bool:
        """init data collector."""
        logger.info("Init mdc...")
        try:
            # for details, please refer to:
            # https://github.com/Azure/azureml_run_specification/blob/mdc_consolidated_spec/specs/model_data_collector.md
            # https://msdata.visualstudio.com/Vienna/_git/sdk-cli-v2?path=/src/azureml-ai-monitoring/README.md&version=GBmain&_a=preview
            from azureml.ai.monitoring import Collector

            self.inputs_collector = Collector(name="model_inputs")
            self.outputs_collector = Collector(name="model_outputs")
            return True
        except ImportError as e:
            logger.warn(f"Load mdc related module failed: {e}")
            return False
        except Exception as e:
            logger.warn(f"Init mdc failed: {e}")
            return False

    def get_flow_file(self):
        """Get flow file from project folder."""
        project_path = Path(self.project_path)
        if (project_path / DEFAULT_FLOW_YAML_FILE).exists():
            flow_file = project_path / DEFAULT_FLOW_YAML_FILE
        elif (project_path / "flow.json").exists():
            # For backward compatibility to support json flow file, will be deprecated
            flow_file = project_path / "flow.json"
        else:
            raise FlowFileNotFound(f"Cannot find flow file in {self.project_path}", target=ErrorTarget.SERVING_APP)
        return flow_file

    def init_executor_if_not_exist(self):
        if not self.executor:
            self.logger.info("Promptflow executor starts initializing...")
            # init the executor if not exist
            coordinator: FlowExecutionCoodinator = FlowExecutionCoodinator.init_from_env()
            # The output may be in streaming mode, which indicates that the tool result might be a generator.
            # By default, run tracker requires only json serializable outputs.
            # We need to add an extra flag to allow generator types to support streaming mode.
            coordinator._run_tracker.allow_generator_types = True
            flow_file = self.get_flow_file()
            runtime = PromptFlowRuntime.get_instance()
            # Set the runtime_mode to serving
            self.logger.info(f"Setting runtime_mode to {RuntimeMode.SERVING!r}..")
            runtime.config.deployment.runtime_mode = RuntimeMode.SERVING
            # Set the operation context deployment config
            oc = OperationContext.get_instance()
            oc.deploy_config = runtime.config.deployment
            # try get the connections
            if runtime.config.deployment.subscription_id:
                # Set edition to enterprise if workspace is provided
                runtime.config.deployment.edition = PromptflowEdition.ENTERPRISE
                self.logger.info("Promptflow serving runtime start getting connections from workspace...")
                connections = prepare_workspace_connections(flow_file, runtime)
                self.logger.info(f"Promptflow serving runtime get connections successfully. keys: {connections.keys()}")
            else:
                # For local test app connections will be set.
                env_connections = os.getenv("PROMPTFLOW_ENCODED_CONNECTIONS", None)
                if not env_connections:
                    self.logger.info("Promptflow serving runtime received no connections from environment!!!")
                    connections = {}
                else:
                    connections = decode_dict(env_connections)
            self.executor = coordinator.create_flow_executor_by_model(flow_file=flow_file, connections=connections)
            self.flow = self.executor._flow
            self.response_fields_to_remove = get_output_fields_to_remove(self.flow, logger)
            self.executor.enable_streaming_for_llm_flow(streaming_response_required)
            self.logger.info("promptflow executor initiated successfully.")

    def init_swagger(self):
        flow_file = self.get_flow_file()
        if flow_file.suffix == ".json":
            flow = Flow.deserialize(load_json(flow_file))
        else:
            flow = Flow.from_yaml(flow_file)
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
    result = app.executor.exec(data)
    if app.mdc_enabled and app.mdc_init_success:
        collect_flow_data(data, result)
    # remove evaluation only fields
    result = {k: v for k, v in result.items() if k not in app.response_fields_to_remove}

    response_creator = ResponseCreator(
        flow_run_result=result,
        accept_mimetypes=request.accept_mimetypes,
    )
    return response_creator.create_response()


def collect_flow_data(input: dict, output: dict):
    """collect flow data via MDC for monitoring."""
    try:
        import pandas as pd

        # collect inputs
        coll_input = {k: [v] for k, v in input.items()}
        input_df = pd.DataFrame(coll_input)
        # collect inputs data, store correlation_context
        context = app.inputs_collector.collect(input_df)
        # collect outputs
        coll_output = {k: [v] for k, v in output.items()}
        output_df = pd.DataFrame(coll_output)
        # collect outputs data, pass in correlation_context so inputs and outputs data can be correlated later
        app.outputs_collector.collect(output_df, context)
    except ImportError as e:
        logger.warn(f"Load mdc related module failed: {e}")
    except Exception as e:
        logger.warn(f"Collect flow data failed: {e}")


def prepare_workspace_connections(flow_file, runtime: PromptFlowRuntime):
    flow_file = Path(flow_file)
    # Resolve connection names from flow.
    logger.info("Reading flow from model ...")
    flow = Flow.from_yaml(flow_file)
    logger.info("Getting connection names for flow ...")
    connection_names = flow.get_connection_names()
    runtime_config = runtime.config.deployment
    from promptflow.runtime.connections import build_connection_dict

    logger.info(f"Getting connection from workspace and build dict for flow ... connection names: {connection_names}")
    # Get workspace connection and return as a dict.
    return build_connection_dict(
        connection_names, runtime_config.subscription_id, runtime_config.resource_group, runtime_config.workspace_name
    )


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
    index_path = Path("index.html")
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
