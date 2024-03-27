# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import hashlib
import io
import json
import os
from pathlib import Path

from flask import Response, current_app, make_response, render_template, send_from_directory, url_for
from ruamel.yaml import YAML
from werkzeug.utils import safe_join

from promptflow._sdk._constants import DEFAULT_ENCODING, PROMPT_FLOW_DIR_NAME, UX_INPUTS_JSON
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import decrypt_flow_path
from promptflow._sdk._utils import json_load, read_write_by_user
from promptflow._utils.flow_utils import is_flex_flow, resolve_flow_path
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.exceptions import UserErrorException

api = Namespace("ui", description="UI")

dict_field = api.schema_model("UIDict", {"additionalProperties": True, "type": "object"})


def create_parser(*args):
    parser = api.parser()
    for arg in args:
        parser.add_argument(
            arg["name"], type=arg["type"], required=arg["required"], location=arg["location"], help=arg["help"]
        )
    return parser


flow_arg = {"name": "flow", "type": str, "required": True, "location": "args", "help": "Path to flow directory."}
experiment_arg = {
    "name": "experiment",
    "type": str,
    "required": False,
    "location": "args",
    "help": "Path to experiment.",
}
base64_data_arg = {
    "name": "base64_data",
    "type": str,
    "required": True,
    "location": "json",
    "help": "Image base64 encoded data.",
}
extension_arg = {
    "name": "extension",
    "type": str,
    "required": True,
    "location": "json",
    "help": "Image file extension.",
}
image_path_arg = {"name": "image_path", "type": str, "required": True, "location": "args", "help": "Path of image."}
inputs_arg = {"name": "inputs", "type": str, "required": True, "location": "json", "help": "The raw YAML content."}
ux_inputs_arg = {"name": "ux_inputs", "type": dict, "required": True, "location": "json", "help": "Flow ux inputs."}

media_save_parser = create_parser(flow_arg, base64_data_arg, extension_arg)
media_get_parser = create_parser(flow_arg, image_path_arg)
yaml_get_parser = create_parser(flow_arg, experiment_arg)
yaml_post_parser = create_parser(flow_arg, experiment_arg, inputs_arg)
flow_ux_input_get_parser = create_parser(flow_arg)
flow_ux_input_post_parser = create_parser(flow_arg, ux_inputs_arg)


@api.route("/chat")
class ChatUI(Resource):
    def get(self):
        return Response(
            render_template("chat_index.html", url_for=url_for),
            mimetype="text/html",
        )


def save_image(directory, base64_data, extension):
    image_data = base64.b64decode(base64_data)
    hash_object = hashlib.sha256(image_data)
    filename = hash_object.hexdigest()
    file_path = Path(directory) / f"{filename}.{extension}"
    with open(file_path, "wb") as f:
        f.write(image_data)
    return file_path


@api.route("/media_save")
class MediaSave(Resource):
    @api.response(code=200, description="Save image", model=fields.String)
    @api.doc(description="Save image")
    @api.expect(media_save_parser)
    def post(self):
        args = media_save_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)
        if os.path.isfile(flow):
            flow = os.path.dirname(flow)
        base64_data = args.base64_data
        extension = args.extension
        safe_path = safe_join(flow, PROMPT_FLOW_DIR_NAME)
        if safe_path is None:
            message = f"The untrusted path {PROMPT_FLOW_DIR_NAME} relative to the base directory {flow} detected!"
            raise UserErrorException(message)
        file_path = save_image(safe_path, base64_data, extension)
        path = Path(file_path).relative_to(flow)
        return str(path)


@api.route("/media")
class MediaView(Resource):
    @api.response(code=200, description="Get image url", model=fields.String)
    @api.doc(description="Get image url")
    def get(self):
        args = media_get_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)
        if os.path.isfile(flow):
            flow = os.path.dirname(flow)
        image_path = args.image_path
        safe_path = safe_join(flow, image_path)
        if safe_path is None:
            message = f"The untrusted path {image_path} relative to the base directory {flow} detected!"
            raise UserErrorException(message)
        safe_path = Path(safe_path).resolve().as_posix()
        if not os.path.exists(safe_path):
            raise UserErrorException("The image doesn't exist")

        directory, filename = os.path.split(safe_path)
        return send_from_directory(directory, filename)


def get_set_flow_yaml(flow, experiment, is_get=True):
    if experiment:
        if os.path.isabs(experiment):
            if is_get is True:
                if not os.path.exists(experiment):
                    raise UserErrorException(f"The absolute experiment file {experiment} doesn't exist")
            flow_path = experiment
        else:
            flow, _ = resolve_flow_path(flow)
            flow_path = safe_join(str(flow), experiment)
            if flow_path is None:
                message = f"The untrusted path {experiment} relative to the base directory {flow} detected!"
                raise UserErrorException(message)
            if is_get is True:
                if not os.path.exists(flow_path):
                    raise UserErrorException(f"The experiment file {flow_path} doesn't exist")
    else:
        if is_get is True:
            if not os.path.exists(flow):
                raise UserErrorException(f"The flow doesn't exist: {flow}")
        flow_path = flow
    return Path(flow_path)


@api.route("/yaml")
class YamlEdit(Resource):
    @api.response(code=200, description="Return flow yam")
    @api.doc(description="Return flow yaml as json")
    @api.produces(["text/yaml"])
    def get(self):
        args = yaml_get_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)
        experiment = args.experiment
        flow_path = get_set_flow_yaml(flow, experiment)
        flow_path_dir, flow_path_file = resolve_flow_path(flow_path)
        flow_info = load_yaml(flow_path_dir / flow_path_file)
        if is_flex_flow(file_path=flow_path_dir / flow_path_file):
            # call api provided by han to get flow input
            flow_input = {}
            flow_info.update(flow_input)
        yaml = YAML()
        string_stream = io.StringIO()  # Create a string stream
        yaml.dump(flow_info, string_stream)  # Use ruamel.yaml to dump YAML data into the string stream
        flow_info = string_stream.getvalue()
        string_stream.close()
        return Response(flow_info, mimetype="text/yaml")

    @api.response(code=200, description="Set the flow yaml content")
    @api.doc(description="Set the flow file content")
    @api.expect(yaml_post_parser)
    def post(self):
        args = yaml_post_parser.parse_args()
        content = args.inputs
        flow = args.flow
        flow = decrypt_flow_path(flow)
        experiment = args.experiment
        flow_path = get_set_flow_yaml(flow, experiment, is_get=False)
        flow_path.touch(mode=read_write_by_user(), exist_ok=True)
        yaml = YAML()
        content = yaml.load(content)
        with open(flow_path, "w") as outfile:
            dump_yaml(content, outfile)
        return make_response(f"{flow_path} content updated successfully", 200)


@api.route("/ux_inputs")
class FlowUxInputs(Resource):
    @api.response(code=200, description="Get the file content of file UX_INPUTS_JSON", model=dict_field)
    @api.doc(description="Get the file content of file UX_INPUTS_JSON")
    def get(self):
        args = flow_ux_input_get_parser.parse_args()
        flow_path = args.flow
        flow_path = decrypt_flow_path(flow_path)
        if not os.path.exists(flow_path):
            raise UserErrorException(f"The flow doesn't exist: {flow_path}")
        flow_path, _ = resolve_flow_path(flow_path)
        flow_ux_inputs_path = flow_path / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON
        if not flow_ux_inputs_path.exists():
            flow_ux_inputs_path.touch(mode=read_write_by_user(), exist_ok=True)
        try:
            ux_inputs = json_load(flow_ux_inputs_path)
        except json.decoder.JSONDecodeError:
            ux_inputs = {}
        return ux_inputs

    @api.response(code=200, description="Set the file content of file UX_INPUTS_JSON")
    @api.doc(description="Set the file content of file UX_INPUTS_JSON")
    @api.expect(flow_ux_input_post_parser)
    def post(self):
        args = flow_ux_input_post_parser.parse_args()
        content = args.ux_inputs
        flow_path = args.flow
        flow_path = decrypt_flow_path(flow_path)
        flow_path, _ = resolve_flow_path(flow_path)
        flow_ux_inputs_path = flow_path / PROMPT_FLOW_DIR_NAME / UX_INPUTS_JSON
        flow_ux_inputs_path.touch(mode=read_write_by_user(), exist_ok=True)
        with open(flow_ux_inputs_path, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        return make_response(f"{flow_ux_inputs_path} content updated successfully", 200)


def serve_trace_ui(path):
    if path != "" and os.path.exists(os.path.join(current_app.static_folder, path)):
        return send_from_directory(current_app.static_folder, path)
    return send_from_directory(current_app.static_folder, "index.html")
