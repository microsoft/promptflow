# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
from functools import wraps

from flask import abort, request


def local_user_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get the user name from request.
        user = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User")
        if user != getpass.getuser():
            abort(403)
        return func(*args, **kwargs)

    return wrapper


def is_port_in_use(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_random_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]
