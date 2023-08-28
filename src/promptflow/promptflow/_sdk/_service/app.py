# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Flask

from promptflow._sdk._service.run import run_bp

app = Flask(__name__)
app.register_blueprint(run_bp)

app.run(debug=True)
