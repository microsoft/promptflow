# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from functools import wraps

from flask import abort, request

from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError
from promptflow.exceptions import PromptflowException, UserErrorException


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


@dataclass
class ErrorInfo:
    exception: InitVar[Exception]

    code: str = field(init=False)
    message: str = field(init=False)
    message_format: str = field(init=False, default=None)
    message_parameters: dict = field(init=False, default=None)
    target: str = field(init=False, default=None)
    module: str = field(init=False, default=None)
    reference_code: str = field(init=False, default=None)
    inner_exception: dict = field(init=False, default=None)
    additional_info: dict = field(init=False, default=None)
    error_codes: list = field(init=False, default=None)

    def __post_init__(self, exception):
        if isinstance(exception, PromptflowException):
            self.code = "PromptflowError"
            if isinstance(exception, (UserErrorException, ConnectionNotFoundError, RunNotFoundError)):
                self.code = "UserError"
            self.message = exception.message
            self.message_format = exception.message_format
            self.message_parameters = exception.message_parameters
            self.target = exception.target
            self.module = exception.module
            self.reference_code = exception.reference_code
            self.inner_exception = exception.inner_exception
            self.additional_info = exception.additional_info
            self.error_codes = exception.error_codes
        else:
            self.code = "ServiceError"
            self.message = str(exception)


@dataclass
class FormattedException:
    exception: InitVar[Exception]
    status_code: InitVar[int] = 500

    error: ErrorInfo = field(init=False)
    time: str = field(init=False)

    def __post_init__(self, exception, status_code):
        self.status_code = status_code
        if isinstance(exception, (UserErrorException, ConnectionNotFoundError, RunNotFoundError)):
            self.status_code = 404
        self.error = ErrorInfo(exception)
        self.time = datetime.now().isoformat()
