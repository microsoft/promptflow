# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask

from promptflow._sdk._service.run import run_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(run_bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
