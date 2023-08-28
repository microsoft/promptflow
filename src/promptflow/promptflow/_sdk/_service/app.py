# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask

from promptflow._sdk._service.run import run_bp

LOCAL_SERVICE_HOST = "0.0.0.0"
LOCAL_SERVICE_PORT = 5000


def create_app():
    app = Flask(__name__)
    app.register_blueprint(run_bp)
    return app


if __name__ == "__main__":
    create_app().run(host=LOCAL_SERVICE_HOST, port=LOCAL_SERVICE_PORT, debug=True)
