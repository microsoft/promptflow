# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import os
import uuid
import json
from flask import make_response, request, send_from_directory

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow._sdk._constants import UX_INPUTS_JSON
from promptflow._sdk._utils import json_load, read_write_by_user, json_dump
from promptflow._utils.yaml_utils import load_yaml
from promptflow._utils.flow_utils import resolve_flow_path
from pathlib import Path

api = Namespace("Flows", description="Flows Management")

# Define flow test request parsing
flow_test_parser = api.parser()
flow_test_parser.add_argument("flow", type=str, location="form", required=True)
flow_test_parser.add_argument("node", type=str, location="form", required=False)
flow_test_parser.add_argument("variant", type=str, location="form", required=False)
flow_test_parser.add_argument("detail", type=str, location="form", required=False, default=None)
flow_test_parser.add_argument("experiment", type=str, location="form", required=False)
flow_test_parser.add_argument("inputs", type=dict, location="form", required=False, default={})
flow_test_parser.add_argument("environment_variables", type=dict, location="form", required=False, default={})

image_save_parser = api.parser()
image_save_parser.add_argument("flow_dir", type=str, location="form", required=True)
image_save_parser.add_argument(
    "base64_data", type=str, location="form", required=True
)
image_save_parser.add_argument(
    "extension", type=str, location="form", required=True
)

image_view_parser = api.parser()
image_view_parser.add_argument("path", type=str, location="form", required=True)

# Response model of flow operation
dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(parser=flow_test_parser, description="Flow test")
    def post(self):
        args = flow_test_parser.parse_args()
        if Configuration.get_instance().is_internal_features_enabled() and args.experiment:
            result = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args.environment_variables,
                variant=args.variant,
                node=args.node,
                experiment=args.experiment,
                output_path=args.detail,
            )
        else:
            result = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args.environment_variables,
                variant=args.variant,
                node=args.node,
                allow_generator_output=False,
                stream_output=False,
                dump_test_result=True,
                output_path=args.detail,
            )
        return result


@api.route("/get")
class FlowGet(Resource):
    @api.response(code=200, description="Get flow snapshot", model=dict_field)
    @api.doc(parser=flow_test_parser, description="Get flow snapshot")
    def get(self):

        args = flow_test_parser.parse_args()
        source_path = Path(args.flow)
        flow_path = resolve_flow_path(source_path)
        flow_info = load_yaml(flow_path)
        return flow_info


@api.route("/ux_inputs")
class FlowUxInputs(Resource):
    @api.response(code=200, description="Get the file content of file UX_INPUTS_JSON", model=dict_field)
    @api.doc(description="Get the file content of file UX_INPUTS_JSON")
    def get(self):
        if not UX_INPUTS_JSON.exists():
            UX_INPUTS_JSON.touch(mode=read_write_by_user(), exist_ok=True)
        try:
            ux_inputs = json_load(UX_INPUTS_JSON)
        except json.decoder.JSONDecodeError:
            ux_inputs = {}
        return ux_inputs

    @api.response(code=200, description="Set the file content of file UX_INPUTS_JSON", model=dict_field)
    @api.doc(description="Set the file content of file UX_INPUTS_JSON")
    def post(self):
        content = request.get_json()
        UX_INPUTS_JSON.touch(mode=read_write_by_user(), exist_ok=True)
        json_dump(content, UX_INPUTS_JSON)
        return make_response("UX_INPUTS_JSON content updated successfully", 200)


def save_image(base64_data, extension, directory):
    image_data = base64.b64decode(base64_data)
    filename = str(uuid.uuid4())
    file_path = os.path.join(directory, f"{filename}.{extension}")
    with open(file_path, "wb") as f:
        f.write(image_data)
    return file_path


@api.route('/image_save')
class ImageSave(Resource):
    @api.response(code=200, description="Save image", model=fields.String)
    @api.doc(parser=image_save_parser, description="Save image")
    def post(self):
        args = image_save_parser.parse_args()
        file_path = save_image(args.base64_data, args.extension, args.flow_dir)
        return make_response(file_path)


@api.route('/image')
class ImageUrl(Resource):
    @api.response(code=200, description="Get image url", model=fields.String)
    @api.doc(parser=image_view_parser, description="Get image url")
    def post(self):
        args = image_view_parser.parse_args()
        image_path = args.path
        if not os.path.exists(image_path):
            return make_response("The image doesn't exist", 404)
        directory, filename = os.path.split(image_path)
        directory = Path(directory).as_posix()
        host, port = request.host.split(':')
        return make_response(f"http://{host}:{port}/v1.0/Flows/image/{str(directory)}/{filename}")


@api.route('/image/<path:directory>/<path:filename>')
class ImageView(Resource):
    @api.doc(description="Visualize image")
    @api.response(code=200, description="Visualize image", model=fields.String)
    def get(self, directory, filename):
        return send_from_directory(directory, filename)
