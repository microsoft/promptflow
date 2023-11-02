import json
import logging

from flask import Flask, jsonify, request

from promptflow import load_flow
from promptflow.entities import FlowContext
from promptflow.exceptions import SystemErrorException, UserErrorException


class SimpleScoreApp(Flask):
    pass


app = SimpleScoreApp(__name__)
logger = logging.getLogger(__name__)


@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, UserErrorException):
        return jsonify({"message": e.message, "additional_info": e.additional_info}), 400
    elif isinstance(e, SystemErrorException):
        return jsonify({"message": e.message, "additional_info": e.additional_info}), 500
    else:
        from promptflow._internal import ErrorResponse, ExceptionPresenter

        # handle other unexpected errors, can use internal class to format them
        # but interface may change in the future
        presenter = ExceptionPresenter.create(e)
        trace_back = presenter.formatted_traceback

        resp = ErrorResponse(presenter.to_dict(include_debug_info=False))
        response_code = resp.response_code
        result = resp.to_simplified_dict()
        result.update({"trace_back": trace_back})
        return jsonify(result), response_code


@app.route("/health", methods=["GET"])
def health():
    """Check if the runtime is alive."""
    return {"status": "Healthy"}


@app.route("/score", methods=["POST"])
def score():
    """process a flow request in the runtime."""
    raw_data = request.get_data()
    logger.info(f"Start loading request data '{raw_data}'.")
    data = json.loads(raw_data)

    # load flow as a function
    f = load_flow("../../../flows/standard/web-classification")
    # configure flow contexts
    if data.get("url"):
        f.context = FlowContext(
            # override flow connections, the overrides may come from the request
            # connections={"classify_with_llm.connection": "another_ai_connection"},
            # override the flow nodes' inputs or other flow configs, the overrides may come from the request
            # **Note**: after this change, node "fetch_text_content_from_url" will take inputs from the
            # following command instead of from flow input
            overrides={"nodes.fetch_text_content_from_url.inputs.url": data["url"]},
        )
    result_dict = f(url="not used")
    # Note: if specified streaming=True in the flow context, the result will be a generator
    # reference promptflow._sdk._serving.response_creator.ResponseCreator on how to handle it in app.
    return jsonify(result_dict)


def create_app(**kwargs):
    return app


if __name__ == "__main__":
    # test this with curl -X POST http://127.0.0.1:5000/score --header "Content-Type: application/json" --data '{\"url\": \"https://www.youtube.com/watch?v=o5ZQyXaAv1g\"}'  # noqa: E501
    create_app().run()
