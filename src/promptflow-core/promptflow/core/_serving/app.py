# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.core._serving.v1.app import PromptflowServingApp, logger
from promptflow.core._serving.v2.app import PromptFlowServingAppV2


def create_app(**kwargs):
    logger.info(f"create_app kwargs: {kwargs}")
    engine = kwargs.pop("engine", "flask")
    if engine == "flask":
        app = PromptflowServingApp(__name__)
        # enable CORS
        try:
            from flask_cors import CORS

            CORS(app)
        except ImportError:
            logger.warning("flask-cors is not installed, CORS is not enabled.")
        # enable auto-instrumentation if customer installed opentelemetry-instrumentation-flask
        try:
            from opentelemetry.instrumentation.flask import FlaskInstrumentor

            FlaskInstrumentor().instrument_app(app, excluded_urls="/swagger.json,/health,/version")
        except ImportError:
            logger.info("opentelemetry-instrumentation-flask is not installed, auto-instrumentation is not enabled.")
        if __name__ != "__main__":
            app.logger.handlers = logger.handlers
            app.logger.setLevel(logger.level)
        app.init(**kwargs)
        return app
    elif engine == "fastapi":
        app = PromptFlowServingAppV2(docs_url=None, redoc_url=None, **kwargs)  # type: ignore
        return app
    else:
        raise ValueError(f"Unsupported engine: {engine}")


if __name__ == "__main__":
    create_app().run()
