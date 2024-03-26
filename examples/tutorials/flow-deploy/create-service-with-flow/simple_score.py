import json
import logging

from flask import Flask, jsonify, request

from promptflow.client import load_flow
from promptflow.connections import AzureOpenAIConnection
from promptflow.entities import FlowContext
from promptflow.exceptions import SystemErrorException, UserErrorException


class SimpleScoreApp(Flask):
    pass


app = SimpleScoreApp(__name__)
logging.basicConfig(format="%(threadName)s:%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# load flow as a function, the function object can be shared accross threads.
f = load_flow("./echo_connection_flow/")


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

    # create a dummy connection object
    # the connection object will only exist in memory and won't store in local db.
    llm_connection = AzureOpenAIConnection(
        name="llm_connection", api_key="[determined by request]", api_base="[determined by request]"
    )

    # configure flow contexts, create a new context object for each request to make sure they are thread safe.
    f.context = FlowContext(
        # override flow connections with connection object created above
        connections={"echo_connection": {"connection": llm_connection}},
        # override the flow nodes' inputs or other flow configs, the overrides may come from the request
        # **Note**: after this change, node "echo_connection" will take input node_input from request
        overrides={"nodes.echo_connection.inputs.node_input": data["node_input"]} if "node_input" in data else {},
    )
    # data in request will be passed to flow as kwargs
    result_dict = f(**data)
    # Note: if specified streaming=True in the flow context, the result will be a generator
    # reference promptflow.core._serving.response_creator.ResponseCreator on how to handle it in app.
    return jsonify(result_dict)


def create_app(**kwargs):
    return app


if __name__ == "__main__":
    # test this with curl -X POST http://127.0.0.1:5000/score --header "Content-Type: application/json" --data '{"flow_input": "some_flow_input", "node_input": "some_node_input"}'  # noqa: E501
    create_app().run(debug=True)
