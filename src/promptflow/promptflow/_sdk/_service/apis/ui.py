# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Response, render_template, url_for
import base64
import os
import uuid
from flask import make_response, request, send_from_directory
from pathlib import Path

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


image_view_model = api.model(
    "ImageView",
    {
        "image_path": fields.String(required=True, description="Path of image."),
    },
)


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
    @api.expect(image_view_model)
    def get(self):
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