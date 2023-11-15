# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
from functools import wraps

from flask import abort, jsonify, request
from flask_restx import fields

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
            response = jsonify({"error_message": f"Internal Server Error"})
            response.status_code = 500
            return response

    return wrapper


def local_user_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get the user name from request.
        user = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User")
        if user != getpass.getuser():
            abort(403)
        return api_wrapper(func)(*args, **kwargs)
    return wrapper


def is_port_in_use(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_random_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class DictItem(fields.Raw):
    def output(self, key, obj, *args, **kwargs):
        try:
            dct = getattr(obj, self.attribute)
        except AttributeError:
            return {}
        return dct or {}
