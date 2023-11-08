# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
from functools import wraps

from flask import abort, jsonify, request

from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError


def api_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            validate_request_user()
            result = func(*args, **kwargs)
            return result
        except (ConnectionNotFoundError, RunNotFoundError):
            response = jsonify({"error_message": "Not Found"})
            response.status_code = 404
            return response
        except Exception as e:  # pylint: disable=broad-except
            response = jsonify({"error_message": f"Internal Server Error, {e}"})
            response.status_code = 500
            return response

    return wrapper


def validate_request_user():
    # Get the user name from request.
    user = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User")
    if user != getpass.getuser():
        abort(403)


def is_port_in_use(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_random_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]
