# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import jsonify, request

from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter
from promptflow.core._serving._errors import NotAcceptable


def handle_error_to_response(e, logger):
    presenter = ExceptionPresenter.create(e)
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


def streaming_response_required():
    """Check if streaming response is required."""
    return "text/event-stream" in request.accept_mimetypes.values()
