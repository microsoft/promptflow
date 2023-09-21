# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import wraps

from flask import jsonify

from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError


def api_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except (ConnectionNotFoundError, RunNotFoundError):
            response = jsonify({"error_message": "Not Found"})
            response.status_code = 404
            return response
        except Exception:  # pylint: disable=broad-except
            response = jsonify({"error_message": "Internal Server Error"})
            response.status_code = 500
            return response

    return wrapper
