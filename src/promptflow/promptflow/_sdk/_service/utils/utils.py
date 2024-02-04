# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import getpass
import socket
import time
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from functools import wraps

import psutil
import requests
from flask import abort, make_response, request

from promptflow._sdk._constants import DEFAULT_ENCODING, HOME_PROMPT_FLOW_DIR, PF_SERVICE_PORT_FILE
from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError
from promptflow._sdk._utils import read_write_by_user
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow._version import VERSION
from promptflow.exceptions import PromptflowException, UserErrorException

logger = get_cli_sdk_logger()


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


def dump_port_to_config(port):
    # Set port to ~/.promptflow/pf.port, if already have a port in file , will overwrite it.
    (HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE).touch(mode=read_write_by_user(), exist_ok=True)
    with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "r", encoding=DEFAULT_ENCODING) as f:
        service_config = load_yaml(f) or {}
    with open(HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE, "w", encoding=DEFAULT_ENCODING) as f:
        service_config["service"] = service_config.get("service", {})
        service_config["service"]["port"] = port
        dump_yaml(service_config, f)


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


def make_response_no_content():
    return make_response("", 204)


def is_pfs_service_healthy(pfs_port) -> bool:
    """Check if pfs service is running."""
    try:
        response = requests.get("http://localhost:{}/heartbeat".format(pfs_port))
        if response.status_code == 200:
            logger.debug(f"Pfs service is already running on port {pfs_port}.")
            return True
    except Exception:  # pylint: disable=broad-except
        pass
    logger.warning(f"Pfs service can't be reached through port {pfs_port}, will try to start/force restart pfs.")
    return False


def check_pfs_service_status(pfs_port, time_delay=5, time_threshold=30) -> bool:
    wait_time = time_delay
    time.sleep(time_delay)
    is_healthy = is_pfs_service_healthy(pfs_port)
    while is_healthy is False and time_threshold > wait_time:
        logger.info(
            f"Pfs service is not ready. It has been waited for {wait_time}s, will wait for at most "
            f"{time_threshold}s."
        )
        wait_time += time_delay
        time.sleep(time_delay)
        is_healthy = is_pfs_service_healthy(pfs_port)
    return is_healthy


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


def build_pfs_user_agent():
    extra_agent = f"local_pfs/{VERSION}"
    if request.user_agent.string:
        return f"{request.user_agent.string} {extra_agent}"
    return extra_agent


def get_client_from_request() -> "PFClient":
    from promptflow._sdk._pf_client import PFClient

    return PFClient(user_agent=build_pfs_user_agent())
