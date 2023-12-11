# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import flask
from jinja2 import Template
from pathlib import Path
from flask import Blueprint, request, url_for, current_app as app


def construct_staticweb_blueprint(static_folder):
    """Construct static web blueprint."""
    staticweb_blueprint = Blueprint('staticweb_blueprint', __name__, static_folder=static_folder)

    @staticweb_blueprint.route("/", defaults={"path": ""}, methods=["GET", "POST"])
    def home():
        """Show the home page."""
        index_path = Path(static_folder) / "index.html"
        if index_path.exists():
            template = Template(open(index_path, "r", encoding="UTF-8").read())
            return flask.render_template(template, url_for=url_for)
        else:
            return "<h1>Welcome to promptflow app.</h1>"

    @staticweb_blueprint.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def notfound(path):
        rules = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}
        if request.path not in rules or request.method not in rules[request.path]:
            unsupported_message = (
                f"The requested api {request.path!r} with {request.method} is not supported by current app, "
                f"if you entered the URL manually please check your spelling and try again."
            )
            return unsupported_message, 404

    return staticweb_blueprint
