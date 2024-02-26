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
        "detail": fields.String(required=False, description="Output path of flow detail"),
        "experiment": fields.String(required=False, description="Path of experiment template"),
        "inputs": fields.Nested(dict_field, required=False),
        "environment_variables": fields.Nested(dict_field, required=False),
    },
)

image_save_model = api.model(
    "ImageSave",
    {
        "flow": fields.String(required=True, description="Path to flow directory."),
        "base64_data": fields.String(required=True, description="Image base64 encoded data."),
        "extension": fields.String(required=True, description="Image file extension."),
    },
)


image_view_model = api.model(
    "ImageView",
    {
        "image_path": fields.String(required=True, description="Path of image."),
    },
)


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
        output_path = api.payload.get("detail", None)
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
        flow_path = api.payload["flow"]
        flow_path = resolve_flow_path(Path(flow_path))
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
    @api.doc(description="Save image")
    @api.expect(image_save_model)
    def post(self):
        flow = api.payload["flow"]
        base64_data = api.payload["base64_data"]
        extension = api.payload["extension"]
        file_path = save_image(base64_data, extension, flow)
        return file_path


@api.route('/image')
class ImageUrl(Resource):
    @api.response(code=200, description="Get image url", model=fields.String)
    @api.doc(description="Get image url")
    @api.expect(image_view_model)
    def post(self):
        image_path = api.payload["image_path"]
        if not os.path.exists(image_path):
            return make_response("The image doesn't exist", 404)
        directory, filename = os.path.split(image_path)
        directory = Path(directory).as_posix()
        return f"{request.base_url}/{str(directory)}/{filename}"


@api.route('/image/<path:directory>/<path:filename>')
class ImageView(Resource):
    @api.doc(description="Visualize image")
    @api.response(code=200, description="Visualize image", model=fields.String)
    def get(self, directory, filename):
        return send_from_directory(directory, filename)
