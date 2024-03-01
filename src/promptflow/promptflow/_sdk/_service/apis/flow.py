# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
from flask import make_response, request
from flask_restx import reqparse
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow._sdk._constants import UX_INPUTS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow._sdk._utils import json_load, read_write_by_user, json_dump
from promptflow._utils.yaml_utils import load_yaml
from promptflow._utils.flow_utils import resolve_flow_path
from pathlib import Path

api = Namespace("Flows", description="Flows Management")


dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})

flow_test_model = api.model(
    "FlowTest",
    {
        "flow": fields.String(required=True, description="Path to flow directory to test."),
        "node": fields.String(required=False, description="If specified it will only test this node, else it will "
                                                          "test the flow."),
        "variant": fields.String(required=False, description="Node & variant name in format of ${"
                                                             "node_name.variant_name}, will use default variant if "
                                                             "not specified."),
        "output_path": fields.String(required=False, description="Output path of flow"),
        "experiment": fields.String(required=False, description="Path of experiment template"),
        "inputs": fields.Nested(dict_field, required=False),
        "environment_variables": fields.Nested(dict_field, required=False),
    },
)

flow_ux_input_model = api.model(
    "FlowUxInput",
    {
        "flow": fields.String(required=True, description="Path to flow directory."),
        "uxInputs": fields.Nested(dict_field, required=True, description="Flow ux inputs"),
    }
)

flow_path_parser = reqparse.RequestParser()
flow_path_parser.add_argument('flow', type=str, required=True, help='Path to flow directory.')


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(description="Flow test")
    @api.expect(flow_test_model)
    def post(self):
        flow = api.payload["flow"]
        inputs = api.payload.get("inputs", None)
        environment_variables = api.payload.get("environment_variables", None)
        variant = api.payload.get("variant", None)
        node = api.payload.get("node", None)
        experiment = api.payload.get("experiment", None)
        output_path = api.payload.get("output_path", None)
        if Configuration.get_instance().is_internal_features_enabled() and experiment:
            result = get_client_from_request().flows.test(
                flow=flow,
                inputs=inputs,
                environment_variables=environment_variables,
                variant=variant,
                node=node,
                experiment=experiment,
                output_path=output_path,
            )
        else:
            result = get_client_from_request().flows.test(
                flow=flow,
                inputs=inputs,
                environment_variables=environment_variables,
                variant=variant,
                node=node,
                allow_generator_output=False,
                stream_output=False,
                dump_test_result=True,
                output_path=output_path,
            )
        return result


@api.route("/get")
class FlowGet(Resource):
    @api.response(code=200, description="Return flow yaml as json", model=dict_field)
    @api.doc(description="Return flow yaml as json")
    def get(self):
        args = flow_path_parser.parse_args()
        flow_path = args.flow
        if not os.path.exists(flow_path):
            return make_response("The flow doesn't exist", 404)
        flow_path = resolve_flow_path(Path(flow_path))
        flow_info = load_yaml(flow_path)
        return flow_info


@api.route("/ux_inputs")
class FlowUxInputs(Resource):
    @api.response(code=200, description="Get the file content of file UX_INPUTS_JSON", model=dict_field)
    @api.doc(description="Get the file content of file UX_INPUTS_JSON")
    def get(self):
        args = flow_path_parser.parse_args()
        flow_path = args.flow
        if not os.path.exists(flow_path):
            return make_response("The flow doesn't exist", 404)
        flow_ux_inputs_path = Path(flow_path) / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON
        if not flow_ux_inputs_path.exists():
            flow_ux_inputs_path.touch(mode=read_write_by_user(), exist_ok=True)
        try:
            ux_inputs = json_load(flow_ux_inputs_path)
        except json.decoder.JSONDecodeError:
            ux_inputs = {}
        return ux_inputs

    @api.response(code=200, description="Set the file content of file UX_INPUTS_JSON", model=dict_field)
    @api.doc(description="Set the file content of file UX_INPUTS_JSON")
    @api.expect(flow_ux_input_model)
    def post(self):
        content = api.payload["uxInputs"]
        flow_path = api.payload["flow"]
        flow_ux_inputs_path = Path(flow_path) / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON
        flow_ux_inputs_path.touch(mode=read_write_by_user(), exist_ok=True)
        json_dump(content, flow_ux_inputs_path)
        return make_response("UX_INPUTS_JSON content updated successfully", 200)
