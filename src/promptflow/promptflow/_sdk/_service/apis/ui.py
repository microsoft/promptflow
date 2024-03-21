# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import hashlib
import os
from pathlib import Path

from flask import Response, current_app, render_template, send_from_directory, url_for
from flask_restx import reqparse
from werkzeug.utils import safe_join

from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import decrypt_flow_path
from promptflow.exceptions import UserErrorException

api = Namespace("ui", description="UI")


media_save_model = api.model(
    "MediaSave",
    {
        "base64_data": fields.String(required=True, description="Image base64 encoded data."),
        "extension": fields.String(required=True, description="Image file extension."),
    },
)

flow_path_parser = reqparse.RequestParser()
flow_path_parser.add_argument("flow", type=str, required=True, location="args", help="Path to flow directory.")

image_path_parser = reqparse.RequestParser()
image_path_parser.add_argument("image_path", type=str, required=True, location="args", help="Path of image.")


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
    @api.expect(media_save_model)
    def post(self):
        args = flow_path_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)
        base64_data = api.payload["base64_data"]
        extension = api.payload["extension"]
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
        args = flow_path_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)

        args = image_path_parser.parse_args()
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


def serve_trace_ui(path):
    if path != "" and os.path.exists(os.path.join(current_app.static_folder, path)):
        return send_from_directory(current_app.static_folder, path)
    return send_from_directory(current_app.static_folder, "index.html")
