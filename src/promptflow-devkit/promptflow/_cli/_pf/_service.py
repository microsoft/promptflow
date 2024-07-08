# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import contextlib
import json
import logging
import os
import platform
import subprocess
import sys

import waitress

from promptflow._cli._params import add_param_ua, add_param_verbose, base_params
from promptflow._cli._utils import activate_action
from promptflow._constants import PF_NO_INTERACTIVE_LOGIN
from promptflow._sdk._constants import (
    HOME_PROMPT_FLOW_DIR,
    PF_SERVICE_DEBUG,
    PF_SERVICE_LOG_FILE,
    PF_SERVICE_WORKER_NUM,
)
from promptflow._sdk._service.app import create_app
from promptflow._sdk._service.utils.utils import (
    check_pfs_service_status,
    dump_port_to_config,
    get_current_env_pfs_file,
    get_pfs_host,
    get_pfs_host_after_check_wildcard,
    get_pfs_version,
    get_port_from_config,
    get_started_service_info,
    hint_stop_before_upgrade,
    is_port_in_use,
    is_run_from_built_binary,
    kill_exist_service,
)
from promptflow._sdk._utilities.general_utils import add_executable_script_to_env_path
from promptflow._utils.logger_utils import get_cli_sdk_logger  # noqa: E402
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()


app = None


def get_app(environ, start_response):
    global app
    if app is None:
        app, _ = create_app()
    if os.environ.get(PF_SERVICE_DEBUG) == "true":
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
    return app.wsgi_app(environ, start_response)


def add_service_parser(subparsers):
    """Add service parser to the pf subparsers."""
    service_parser = subparsers.add_parser(
        "service",
        description="Manage prompt flow service, which offers chat and trace UI functionalities.",
        help="Manage prompt flow service.",
    )
    service_subparsers = service_parser.add_subparsers()
    add_parser_start_service(service_subparsers)
    add_parser_stop_service(service_subparsers)
    add_parser_show_service(service_subparsers)
    service_parser.set_defaults(action="service")


def dispatch_service_commands(args: argparse.Namespace):
    if args.sub_action == "start":
        start_service(args)
    elif args.sub_action == "stop":
        stop_service()
    elif args.sub_action == "status":
        show_service()


def add_parser_start_service(subparsers):
    """Add service start parser to the pf service subparsers."""
    epilog = """
    Examples:

    # Start prompt flow service:
    pf service start
    # Force restart prompt flow service:
    pf service start --force
    # Start prompt flow service with specific port:
    pf service start --port 65535
    """  # noqa: E501
    add_param_port = lambda parser: parser.add_argument(  # noqa: E731
        "-p",
        "--port",
        type=int,
        help="The designated port of the prompt flow service and port number will be remembered if port is available.",
    )
    add_param_force = lambda parser: parser.add_argument(  # noqa: E731
        "--force",
        action="store_true",
        help="If the port is used, the existing service will be terminated and restart a new service.",
    )
    add_param_debug = lambda parser: parser.add_argument(  # noqa: E731
        "-d",
        "--debug",
        action="store_true",
        help="Start the prompt flow service in foreground, displaying debug level logs directly in the terminal.",
    )
    activate_action(
        name="start",
        description="Prompt Flow attempts to launch the service on the default port 23333. If occupied, it probes "
        "consecutive ports, increasing by one each time. The port number is retained for future service "
        "startups.",
        epilog=epilog,
        add_params=[
            add_param_port,
            add_param_force,
            add_param_debug,
        ]
        + [add_param_ua, add_param_verbose],
        subparsers=subparsers,
        help_message="Start prompt flow service.",
        action_param_name="sub_action",
    )


def add_parser_stop_service(subparsers):
    """Add service stop parser to the pf service subparsers."""
    epilog = """
    Examples:

    # Stop prompt flow service:
    pf service stop
    """  # noqa: E501
    activate_action(
        name="stop",
        description="Stop prompt flow service.",
        epilog=epilog,
        add_params=base_params,
        subparsers=subparsers,
        help_message="Stop prompt flow service.",
        action_param_name="sub_action",
    )


def add_parser_show_service(subparsers):
    """Add service show parser to the pf service subparsers."""
    epilog = """
    Examples:

    # Display the started prompt flow service info.:
    pf service status
    """  # noqa: E501
    activate_action(
        name="status",
        description="Show the started prompt flow service status.",
        epilog=epilog,
        add_params=base_params,
        subparsers=subparsers,
        help_message="Show the started prompt flow service status.",
        action_param_name="sub_action",
    )


def start_service(args):
    # User Agent will be set based on header in request, so not set globally here.
    os.environ[PF_NO_INTERACTIVE_LOGIN] = "true"
    port = args.port
    service_host = get_pfs_host()
    if args.debug:
        os.environ[PF_SERVICE_DEBUG] = "true"
        if not is_run_from_built_binary():
            add_executable_script_to_env_path()
        port = _prepare_app_for_foreground_service(port, args.force, service_host)
        waitress.serve(app, host=service_host, port=port, threads=PF_SERVICE_WORKER_NUM)
    else:
        if is_run_from_built_binary():
            # For msi installer/executable, use sdk api to start pfs since it's not supported to invoke waitress by cli
            # directly after packaged by Pyinstaller.
            parent_dir = os.path.dirname(sys.executable)
            output_path = os.path.join(parent_dir, "output.txt")
            with redirect_stdout_to_file(output_path):
                port = _prepare_app_for_foreground_service(port, args.force, service_host)
            waitress.serve(app, host=service_host, port=port, threads=PF_SERVICE_WORKER_NUM)
        else:
            port = validate_port(port, args.force, service_host)
            add_executable_script_to_env_path()
            # Start a pfs process using detach mode. It will start a new process and create a new app. So we use
            # environment variable to pass the debug mode, since it will inherit parent process environment variable.
            if platform.system() == "Windows":
                _start_background_service_on_windows(port, service_host)
            else:
                _start_background_service_on_unix(port, service_host)
            host = get_pfs_host_after_check_wildcard(service_host)
            is_healthy = check_pfs_service_status(port, host)
            if is_healthy:
                message = f"Start prompt flow service on {service_host}:{port}, version: {get_pfs_version()}."
                print(message)
                logger.info(message)
            else:
                logger.warning(f"Prompt flow service start failed in {port}. {hint_stop_before_upgrade}")


def validate_port(port, force_start, service_host):
    if port:
        _validate_port(port, force_start, service_host)
        # dump port to config file only when port is valid or force_start is True.
        dump_port_to_config(port)
    else:
        host = get_pfs_host_after_check_wildcard(service_host)
        port = get_port_from_config(host, create_if_not_exists=True)
        _validate_port(port, force_start, service_host)
    return port


def _validate_port(port, force_start, service_host):
    host = get_pfs_host_after_check_wildcard(service_host)
    if is_port_in_use(port, host):
        if force_start:
            message = f"Force restart the service on the {service_host}:{port}."
            if is_run_from_built_binary():
                print(message)
            logger.warning(message)
            kill_exist_service(port)
        else:
            message = f"Service {service_host}:{port} is used."
            if is_run_from_built_binary():
                print(message)
            logger.warning(message)
            raise UserErrorException(f"Service {service_host}:{port} is used.")


@contextlib.contextmanager
def redirect_stdout_to_file(path):
    # For msi installer, use vbs to start pfs in a hidden window. But it doesn't support redirect output in the
    # hidden window to terminal. So we redirect output to a file. And then print the file content to terminal in
    # pfs.bat.
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        with open(path, "w") as file:
            sys.stdout = file
            sys.stderr = file
            yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def _prepare_app_for_foreground_service(port, force_start, service_host):
    port = validate_port(port, force_start, service_host)
    global app
    if app is None:
        app, _ = create_app()
    if os.environ.get(PF_SERVICE_DEBUG) == "true":
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
    message = f"Starting prompt flow Service on {service_host}:{port}, version: {get_pfs_version()}."
    app.logger.info(message)
    print(message)
    return port


def _start_background_service_on_windows(port, service_host):
    try:
        import win32api
        import win32con
        import win32process
    except ImportError as ex:
        raise UserErrorException(
            f"Please install pywin32 by 'pip install pywin32' and retry. prompt flow "
            f"service start depends on pywin32.. {ex}"
        )
    command = (
        f"waitress-serve --listen={service_host}:{port} --threads={PF_SERVICE_WORKER_NUM} "
        "promptflow._cli._pf._service:get_app"
    )
    logger.debug(f"Start prompt flow service in Windows: {command}")
    startupinfo = win32process.STARTUPINFO()
    startupinfo.dwFlags |= win32process.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = win32con.SW_HIDE
    process_attributes = None
    thread_attributes = None
    inherit_handles = False
    creation_flags = win32con.CREATE_NEW_PROCESS_GROUP | win32con.DETACHED_PROCESS
    environment = None
    current_directory = None
    process_handle, thread_handle, process_id, thread_id = win32process.CreateProcess(
        None,
        command,
        process_attributes,
        thread_attributes,
        inherit_handles,
        creation_flags,
        environment,
        current_directory,
        startupinfo,
    )

    win32api.CloseHandle(process_handle)
    win32api.CloseHandle(thread_handle)


def _start_background_service_on_unix(port, service_host):
    cmd = [
        "waitress-serve",
        f"--listen={service_host}:{port}",
        f"--threads={PF_SERVICE_WORKER_NUM}",
        "promptflow._cli._pf._service:get_app",
    ]
    logger.debug(f"Start prompt flow service in Unix: {cmd}")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, start_new_session=True)


def stop_service():
    service_host = get_pfs_host()
    port = get_port_from_config(service_host)
    host = get_pfs_host_after_check_wildcard(service_host)
    if port is not None and is_port_in_use(port, host):
        kill_exist_service(port)
        message = f"Prompt flow service stop on {service_host}:{port}."
    else:
        message = "Prompt flow service is not started."
    logger.debug(message)
    print(message)


def show_service():
    service_host = get_pfs_host()
    port = get_port_from_config(service_host)
    status = get_started_service_info(port)
    if is_run_from_built_binary():
        log_file = HOME_PROMPT_FLOW_DIR / PF_SERVICE_LOG_FILE
    else:
        log_file = get_current_env_pfs_file(PF_SERVICE_LOG_FILE)
    if status:
        extra_info = {"service_host": service_host, "log_file": log_file.as_posix(), "version": get_pfs_version()}
        status.update(extra_info)
        dumped_status = json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
        print(dumped_status)
        return
    else:
        logger.warning(
            f"Prompt flow service is not started. The prompt flow service log is located at {log_file.as_posix()} "
            f"and prompt flow version is {get_pfs_version()}."
        )
