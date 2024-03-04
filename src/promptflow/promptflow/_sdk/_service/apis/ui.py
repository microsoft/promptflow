# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Response, render_template, url_for
from flask_restx import reqparse
import base64
import os
import uuid
from flask import make_response, request, send_from_directory
from pathlib import Path
from werkzeug.utils import safe_join

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR
from promptflow._sdk._service import Namespace, Resource, fields

api = Namespace("ui", description="UI")

media_save_model = api.model(
    "MediaSave",
    {
        "base64_data": fields.String(required=True, description="Image base64 encoded data."),
        "extension": fields.String(required=True, description="Image file extension."),
    },
)

image_path_parser = reqparse.RequestParser()
image_path_parser.add_argument('image_path', type=str, required=True, help='Path of image.')


@api.route("/traces")
class TraceUI(Resource):
    def get(self):
        return Response(
            render_template("index.html", url_for=url_for),
            mimetype="text/html",
        )


def save_image(base64_data, extension):
    image_data = base64.b64decode(base64_data)
    filename = str(uuid.uuid4())
    file_path = HOME_PROMPT_FLOW_DIR / f"{filename}.{extension}"
    with open(file_path, "wb") as f:
        f.write(image_data)
    return str(file_path)


@api.route('/media_save')
class MediaSave(Resource):
    @api.response(code=200, description="Save image", model=fields.String)
    @api.doc(description="Save image")
    @api.expect(media_save_model)
    def post(self):
        base64_data = api.payload["base64_data"]
        extension = api.payload["extension"]
        file_path = save_image(base64_data, extension)
        return file_path


@api.route('/image')
class ImageUrl(Resource):
    @api.response(code=200, description="Get image url", model=fields.String)
    @api.doc(description="Get image url")
    def get(self):
        args = image_path_parser.parse_args()
        image_path = Path(args.image_path).as_posix()
        home_prompt_flow_dir = HOME_PROMPT_FLOW_DIR.as_posix()

        if not image_path.startswith(home_prompt_flow_dir):
            return make_response(f"Can only access images in the restricted directory: {home_prompt_flow_dir}", 403)

        if not os.path.exists(image_path):
            return make_response("The image doesn't exist", 404)
        directory, filename = os.path.split(image_path)
        directory = Path(directory).as_posix()
        return f"{request.base_url}/{str(directory)}/{filename}"


@api.route('/image/<path:filepath>')
class ImageView(Resource):
    @api.doc(description="Visualize image")
    @api.response(code=200, description="Visualize image", model=fields.String)
    def get(self, filepath):
        directory, filename = os.path.split(filepath)
        directory = Path(directory).as_posix()
        home_prompt_flow_dir = HOME_PROMPT_FLOW_DIR.as_posix()
        if directory != home_prompt_flow_dir:
            return make_response(f"Can only access images in the restricted directory: {home_prompt_flow_dir}", 403)

        image_path = safe_join(directory, filename)
        if image_path is None:
            return make_response("Invalid path", 400)

        return send_from_directory(directory, filename)
