# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os

from flask import jsonify, request

from promptflow._sdk._serving._errors import (
    JsonPayloadRequiredForMultipleInputFields,
    MissingRequiredFlowInput,
    NotAcceptable,
)
from promptflow.contracts.flow import Flow as FlowContract
from promptflow.exceptions import ErrorResponse, ErrorTarget, ExceptionPresenter


def load_request_data(flow, raw_data, logger):
    try:
        data = json.loads(raw_data)
    except Exception:
        input = None
        if flow.inputs.keys().__len__() > 1:
            # this should only work if there's only 1 input field, otherwise it will fail
            # TODO: add a check to make sure there's only 1 input field
            message = (
                "Promptflow executor received non json data, but there's more than 1 input fields, "
                "please use json request data instead."
            )
            raise JsonPayloadRequiredForMultipleInputFields(message, target=ErrorTarget.SERVING_APP)
        if isinstance(raw_data, bytes) or isinstance(raw_data, bytearray):
            input = str(raw_data, "UTF-8")
        elif isinstance(raw_data, str):
            input = raw_data
        default_key = list(flow.inputs.keys())[0]
        logger.info(f"Promptflow executor received non json data: {input}, default key: {default_key}")
        data = {default_key: input}
    return data


def validate_request_data(flow, data):
    """Validate required request data is provided."""
    # TODO: Note that we don't have default flow input presently, all of the default is None.
    required_inputs = [k for k, v in flow.inputs.items() if v.default is None]
    missing_inputs = [k for k in required_inputs if k not in data]
    if missing_inputs:
        raise MissingRequiredFlowInput(
            f"Required input fields {missing_inputs} are missing in request data {data!r}",
            target=ErrorTarget.SERVING_APP,
        )


def streaming_response_required():
    """Check if streaming response is required."""
    return "text/event-stream" in request.accept_mimetypes.values()


def get_sample_json(project_path, logger):
    # load swagger sample if exists
    sample_file = os.path.join(project_path, "samples.json")
    if not os.path.exists(sample_file):
        return None
    logger.info("Promptflow sample file detected.")
    with open(sample_file, "r", encoding="UTF-8") as f:
        sample = json.load(f)
    return sample


# get evaluation only fields
def get_output_fields_to_remove(flow: FlowContract, logger) -> list:
    """get output fields to remove."""
    included_outputs = os.getenv("PROMPTFLOW_RESPONSE_INCLUDED_FIELDS", None)
    if included_outputs:
        logger.info(f"Response included fields: {included_outputs}")
        res = json.loads(included_outputs)
        return [k for k, v in flow.outputs.items() if k not in res]
    return [k for k, v in flow.outputs.items() if v.evaluation_only]


def handle_error_to_response(e, logger):
    presenter = ExceptionPresenter(e)
    logger.error(f"Promptflow serving app error: {presenter.to_dict()}")
    logger.error(f"Promptflow serving error traceback: {presenter.formatted_traceback}")
    resp = ErrorResponse(presenter.to_dict())
    response_code = resp.response_code
    # The http response code for NotAcceptable is 406.
    # Currently the error framework does not allow response code overriding,
    # we add a check here to override the response code.
    # TODO: Consider how to embed this logic into the error framework.
    if isinstance(e, NotAcceptable):
        response_code = 406
    return jsonify(resp.to_simplified_dict()), response_code
