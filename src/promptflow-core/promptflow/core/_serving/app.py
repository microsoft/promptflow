# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._utils.logger_utils import LoggerFactory


def create_app(**kwargs):
    engine = kwargs.pop("engine", "flask")
    if engine == "flask":
        from promptflow.core._serving.v1.app import PromptflowServingApp

        logger = LoggerFactory.get_logger("pfserving-app", target_stdout=True)
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
        app.init(logger=logger, **kwargs)
        return app
    elif engine == "fastapi":
        # use local import to avoid importing fastapi if not necessary
        from promptflow.core._serving.v2.app import PromptFlowServingAppV2

        logger = LoggerFactory.get_logger("pfserving-app-v2", target_stdout=True)
        # TODO: support specify flow file path in fastapi app
        app = PromptFlowServingAppV2(docs_url=None, redoc_url=None, logger=logger, **kwargs)  # type: ignore
        # enable auto-instrumentation if customer installed opentelemetry-instrumentation-fastapi
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app, excluded_urls="/swagger.json,/health,/version")
        except ImportError:
            logger.info("opentelemetry-instrumentation-fastapi is not installed, auto-instrumentation is not enabled.")
        return app
    else:
        raise ValueError(f"Unsupported engine: {engine}")


if __name__ == "__main__":
    create_app().run()
