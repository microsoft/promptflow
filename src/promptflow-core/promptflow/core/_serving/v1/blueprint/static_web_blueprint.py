# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

import flask
from flask import Blueprint
from flask import current_app as app
from flask import request, url_for
from jinja2 import Template


def construct_staticweb_blueprint(static_folder):
    """Construct static web blueprint."""
    staticweb_blueprint = Blueprint("staticweb_blueprint", __name__, static_folder=static_folder)

    @staticweb_blueprint.route("/", methods=["GET", "POST"])
    def home():
        """Show the home page."""
        index_path = Path(static_folder) / "index.html" if static_folder else None
        if index_path and index_path.exists():
            template = Template(open(index_path, "r", encoding="UTF-8").read())
            return flask.render_template(template, url_for=url_for)
        else:
            return "<h1>Welcome to promptflow app.</h1>"

    @staticweb_blueprint.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def notfound(path):
        rules = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
        if path not in rules or request.method not in rules[path]:
            unsupported_message = (
                f"The requested api {path!r} with {request.method} is not supported by current app, "
                f"if you entered the URL manually please check your spelling and try again."
            )
            return unsupported_message, 404

    return staticweb_blueprint
