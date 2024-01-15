# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from functools import wraps

import psutil
from flask import abort, request

from promptflow._sdk._constants import DEFAULT_ENCODING, HOME_PROMPT_FLOW_DIR, PF_SERVICE_PORT_FILE
from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError
from promptflow._sdk._utils import read_write_by_user
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
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


def get_port_from_config(create_if_not_exists=False):
    (HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE).touch(mode=read_write_by_user(), exist_ok=True)
    with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "r", encoding=DEFAULT_ENCODING) as f:
        service_config = load_yaml(f) or {}
        port = service_config.get("service", {}).get("port", None)
    if not port and create_if_not_exists:
        with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "w", encoding=DEFAULT_ENCODING) as f:
            # Set random port to ~/.promptflow/pf.yaml
            port = get_random_port()
            service_config["service"] = service_config.get("service", {})
            service_config["service"]["port"] = port
            dump_yaml(service_config, f)
    return port


def is_port_in_use(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def get_random_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _get_process_by_port(port):
    for proc in psutil.process_iter(["pid", "connections", "create_time"]):
        try:
            for connection in proc.connections():
                if connection.laddr.port == port:
                    return proc
        except psutil.AccessDenied:
            pass


def kill_exist_service(port):
    proc = _get_process_by_port(port)
    if proc:
        proc.terminate()
        proc.wait(10)


def get_started_service_info(port):
    service_info = {}
    proc = _get_process_by_port(port)
    if proc:
        create_time = proc.info["create_time"]
        process_uptime = datetime.now() - datetime.fromtimestamp(create_time)
        service_info["create_time"] = str(datetime.fromtimestamp(create_time))
        service_info["uptime"] = str(process_uptime)
        service_info["port"] = port
    return service_info


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
