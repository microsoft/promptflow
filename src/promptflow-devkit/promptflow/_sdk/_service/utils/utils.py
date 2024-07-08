# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import getpass
import hashlib
import os
import platform
import re
import socket
import subprocess
import sys
import time
import traceback
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path

import psutil
import requests
from flask import abort, make_response, request

from promptflow._constants import PF_RUN_AS_BUILT_BINARY
from promptflow._sdk._constants import (
    DEFAULT_ENCODING,
    HOME_PROMPT_FLOW_DIR,
    PF_SERVICE_DEFAULT_PORT,
    PF_SERVICE_HOST,
    PF_SERVICE_LOG_FILE,
    PF_SERVICE_PORT_DIT_NAME,
    PF_SERVICE_PORT_FILE,
    PF_SERVICE_WILDCARD_ADDRESS,
)
from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError
from promptflow._sdk._utilities.general_utils import (
    get_promptflow_devkit_version,
    get_promptflow_sdk_version,
    read_write_by_user,
)
from promptflow._sdk._version import VERSION
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.exceptions import PromptflowException, UserErrorException

logger = get_cli_sdk_logger()

hint_stop_message = "You can stop the prompt flow service with the following command:'\033[1mpf service stop\033[0m'.\n"
hint_stop_before_upgrade = (
    "Kindly reminder: If you have previously upgraded the prompt flow package , please "
    "double-confirm that you have run '\033[1mpf service stop\033[0m' to stop the prompt flow"
    "service before proceeding with the upgrade. Otherwise, you may encounter unexpected "
    "environmental issues or inconsistencies between the version of running prompt flow service "
    "and the local prompt flow version. Alternatively, you can use the "
    "'\033[1mpf upgrade\033[0m' command to proceed with the upgrade process for the prompt flow "
    "package."
)


def local_user_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get the user name from request.
        user = request.environ.get("REMOTE_USER") or request.headers.get("X-Remote-User")
        if user != getpass.getuser():
            abort(403)
        return func(*args, **kwargs)

    return wrapper


def get_current_env_pfs_file(file_name):
    executable_path = Path(sys.executable.lower()).as_posix()
    dir_name = os.path.basename(os.path.dirname(executable_path))
    # Hash the executable path
    hash_object = hashlib.sha1(executable_path.encode())
    hex_dig = hash_object.hexdigest()
    port_file_name = f"{dir_name}_{hex_dig}_{file_name}"
    port_file_dir = HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_DIT_NAME
    port_file_dir.mkdir(parents=True, exist_ok=True)
    port_file_path = port_file_dir / port_file_name
    port_file_path.touch(mode=read_write_by_user(), exist_ok=True)
    return port_file_path


def get_port_from_config(service_host, create_if_not_exists=False):
    port_file_path = get_port_file_location()
    with open(port_file_path, "r+", encoding=DEFAULT_ENCODING) as f:
        service_config = load_yaml(f) or {}
        port = service_config.get("service", {}).get("port", None)
        if not port and create_if_not_exists:
            port = get_pfs_port(service_host)
            service_config["service"] = service_config.get("service", {})
            service_config["service"]["port"] = port
            logger.debug(f"Set port {port} to file {port_file_path}")
            f.seek(0)  # Move the file pointer to the beginning of the file
            dump_yaml(service_config, f)
            f.truncate()  # Remove any remaining content
    return port


def get_port_file_location():
    if is_run_from_built_binary():
        port_file_path = HOME_PROMPT_FLOW_DIR / PF_SERVICE_PORT_FILE
        port_file_path.touch(mode=read_write_by_user(), exist_ok=True)
    else:
        port_file_path = get_current_env_pfs_file(PF_SERVICE_PORT_FILE)
    return port_file_path


def dump_port_to_config(port):
    port_file_path = get_port_file_location()
    # Set port to ~/.promptflow/pfs/**_pf.port, if already have a port in file , will not write again.
    with open(port_file_path, "r+", encoding=DEFAULT_ENCODING) as f:
        service_config = load_yaml(f) or {}
        service_config["service"] = service_config.get("service", {})
        if service_config["service"].get("port", None) != port:
            service_config["service"]["port"] = port
            logger.debug(f"Set port {port} to file {port_file_path}")
            f.seek(0)  # Move the file pointer to the beginning of the file
            dump_yaml(service_config, f)
            f.truncate()  # Remove any remaining content


def is_port_in_use(port: int, service_host: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # OS will wait for timeout when connecting to an unused port, so it will take about 2s. Set timeout here to
        # avoid long waiting time
        s.settimeout(0.1)
        return s.connect_ex((service_host, port)) == 0


def get_pfs_port(service_host):
    port = PF_SERVICE_DEFAULT_PORT
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((service_host, port))
                return s.getsockname()[1]
        except OSError:
            port += 1


def get_log_file_location():
    # each env will have its own log file
    if is_run_from_built_binary():
        log_file = HOME_PROMPT_FLOW_DIR / PF_SERVICE_LOG_FILE
        log_file.touch(mode=read_write_by_user(), exist_ok=True)
    else:
        log_file = get_current_env_pfs_file(PF_SERVICE_LOG_FILE)
    return log_file


def _get_process_by_port(port):
    if platform.system() == "Windows":
        command = f"netstat -ano | findstr :{port}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip()
            lines = output.split("\n")
            for line in lines:
                if "LISTENING" in line:
                    pid = line.split()[-1]  # get the PID
                    return psutil.Process(int(pid))
    else:  # Linux and macOS
        command = f"lsof -i :{port} -sTCP:LISTEN | awk 'NR>1 {{print $2}}'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip()
            pid = output.split("\n")[0]  # get the first PID
            if pid != "":
                return psutil.Process(int(pid))


def kill_exist_service(port):
    proc = _get_process_by_port(port) if port else None
    if proc:
        proc.terminate()
        proc.wait(10)


def get_started_service_info(port):
    service_info = {}
    proc = _get_process_by_port(port) if port else None
    if proc:
        create_time = proc.create_time()
        process_uptime = datetime.now() - datetime.fromtimestamp(create_time)
        service_info["create_time"] = str(datetime.fromtimestamp(create_time))
        service_info["uptime"] = str(process_uptime)
        service_info["port"] = port
    return service_info


def make_response_no_content():
    return make_response("", 204)


def get_pfs_version():
    """Prompt flow service show promptflow version if installed from root, else devkit version"""
    version_promptflow = get_promptflow_sdk_version()
    if version_promptflow:
        return version_promptflow
    else:
        version_devkit = get_promptflow_devkit_version()
        return version_devkit


def is_pfs_service_healthy(pfs_port, service_host) -> bool:
    """Check if pfs service is running and pfs version matches pf version."""
    try:
        response = requests.get(f"http://{service_host}:{pfs_port}/heartbeat")
        if response.status_code == 200:
            logger.debug(f"Prompt flow service is already running on {service_host}:{pfs_port}, {response.text}")
            match = re.search(r'"promptflow":"(.*?)"', response.text)
            if match:
                version = match.group(1)
                local_version = get_pfs_version()
                is_healthy = version == local_version
                if not is_healthy:
                    logger.warning(
                        f"Prompt flow service is running on {service_host}:{pfs_port}, but the version is not the "
                        f"same as local sdk version {local_version}. The service version is {version}."
                    )
            else:
                is_healthy = False
                logger.warning("/heartbeat response doesn't contain current prompt flow service version.")
            return is_healthy
    except Exception:  # pylint: disable=broad-except
        pass
    logger.debug(f"Failed to call prompt flow service api /heartbeat on {service_host}:{pfs_port}.")
    return False


def check_pfs_service_status(pfs_port, service_host, time_delay=1, count_threshold=10) -> bool:
    cnt = 1
    time.sleep(time_delay)
    is_healthy = is_pfs_service_healthy(pfs_port, service_host)
    while is_healthy is False and count_threshold > cnt:
        message = (
            f"Waiting for the prompt flow service status to become healthy... It has been tried for {cnt} times, will "
            f"try at most {count_threshold} times."
        )
        if cnt >= 3:
            logger.warning(message)
        else:
            logger.info(message)
        cnt += 1
        time.sleep(time_delay)
        is_healthy = is_pfs_service_healthy(pfs_port, service_host)
    return is_healthy


def get_pfs_host():
    """Get the host of prompt flow service."""
    from promptflow._sdk._configuration import Configuration

    config = Configuration.get_instance()
    pfs_host = config.get_pfs_host()
    logger.debug("resolved service.host: %s", pfs_host)
    return pfs_host


def get_pfs_host_after_check_wildcard(service_host):
    """When the address is 0.0.0.0, return the default host."""
    return PF_SERVICE_HOST if service_host == PF_SERVICE_WILDCARD_ADDRESS else service_host


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
            self.message_parameters = {k: str(v) for k, v in exception.message_parameters.items()}
            self.target = exception.target
            self.module = exception.module
            self.reference_code = exception.reference_code
            # If not inner_exception here, directly get traceback here
            self.inner_exception = (
                str(exception.inner_exception) if exception.inner_exception else traceback.format_exc()
            )
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
    user_agent = request.user_agent.string
    user_agent_for_local_pfs = f"local_pfs/{VERSION}"
    if user_agent:
        return f"{user_agent} {user_agent_for_local_pfs}"
    return user_agent_for_local_pfs


def get_client_from_request(*, connection_provider=None) -> "PFClient":
    """
    Build a PFClient instance based on current request in local PFS.

    User agent may be different for each request.
    """
    from promptflow._sdk._pf_client import PFClient

    user_agent = build_pfs_user_agent()

    if connection_provider:
        pf_client = PFClient(connection_provider=connection_provider, user_agent_override=user_agent)
    else:
        pf_client = PFClient(user_agent_override=user_agent)
    return pf_client


def is_run_from_built_binary():
    """
    Use this function to trigger behavior difference between calling from prompt flow sdk/cli and built binary.

    Allow customer to use environment variable to control the triggering.
    """
    return (
        sys.executable.endswith("pfcli.exe")
        or sys.executable.endswith("app.exe")
        or sys.executable.endswith("app")
        or os.environ.get(PF_RUN_AS_BUILT_BINARY, "").lower() == "true"
    )


def encrypt_flow_path(flow_path):
    return base64.urlsafe_b64encode(flow_path.encode()).decode()


def decrypt_flow_path(encrypted_flow_path):
    return base64.urlsafe_b64decode(encrypted_flow_path).decode()
