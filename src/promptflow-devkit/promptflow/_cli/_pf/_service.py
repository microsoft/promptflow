# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import contextlib
import logging
import os
import platform
import subprocess
import sys

import waitress

from promptflow._cli._params import base_params
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
    add_executable_script_to_env_path,
    check_pfs_service_status,
    dump_port_to_config,
    get_current_env_pfs_file,
    get_pfs_version,
    get_port_from_config,
    get_started_service_info,
    hint_stop_before_upgrade,
    is_port_in_use,
    is_run_from_built_binary,
    kill_exist_service,
)
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
    elif args.sub_action == "show-status":
        show_service()


def add_parser_start_service(subparsers):
    """Add service start parser to the pf service subparsers."""
    epilog = """
    Examples:

    # Start prompt flow service:
    pf service start
    # Force restart promptflow service:
    pf service start --force
    # Start promptflow service with specific port:
    pf service start --port 65553
    """  # noqa: E501
    add_param_port = lambda parser: parser.add_argument(  # noqa: E731
        "-p", "--port", type=int, help="port of the promptflow service"
    )
    add_param_force = lambda parser: parser.add_argument(  # noqa: E731
        "--force",
        action="store_true",
        help="If the port is used, the existing service will be terminated and restart a new service.",
    )
    activate_action(
        name="start",
        description="Start prompt flow service.",
        epilog=epilog,
        add_params=[
            add_param_port,
            add_param_force,
        ]
        + base_params,
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
    pf service show-status
    """  # noqa: E501
    activate_action(
        name="show-status",
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
    if args.debug:
        os.environ[PF_SERVICE_DEBUG] = "true"

    if is_run_from_built_binary():
        # For msi installer/executable, use sdk api to start pfs since it's not supported to invoke waitress by cli
        # directly after packaged by Pyinstaller.
        parent_dir = os.path.dirname(sys.executable)
        output_path = os.path.join(parent_dir, "output.txt")
        with redirect_stdout_to_file(output_path):
            validate_port(port, args.force)
            global app
            if app is None:
                app, _ = create_app()
            if os.environ.get(PF_SERVICE_DEBUG) == "true":
                app.logger.setLevel(logging.DEBUG)
            else:
                app.logger.setLevel(logging.INFO)
            message = f"Starting Prompt Flow Service on {port}, version: {get_pfs_version()}."
            app.logger.info(message)
            print(message)
            sys.stdout.flush()
        waitress.serve(app, host="127.0.0.1", port=port, threads=PF_SERVICE_WORKER_NUM)
    else:
        validate_port(port, args.force)
        add_executable_script_to_env_path()
        # Start a pfs process using detach mode. It will start a new process and create a new app. So we use environment
        # variable to pass the debug mode, since it will inherit parent process environment variable.
        if platform.system() == "Windows":
            _start_detach_service_in_win(port)
        else:
            _start_detach_service_in_unix(port)
        is_healthy = check_pfs_service_status(port)
        if is_healthy:
            message = f"Start Promptflow Service on port {port}, version: {get_pfs_version()}."
            print(message)
            logger.info(message)
        else:
            logger.warning(f"Promptflow service start failed in {port}. {hint_stop_before_upgrade}")


def validate_port(port, force_start):
    if port:
        dump_port_to_config(port)
        _validate_port(port, force_start)
    else:
        port = get_port_from_config(create_if_not_exists=True)
        _validate_port(port, force_start)


def _validate_port(port, force_start):
    if is_port_in_use(port):
        if force_start:
            message = f"Force restart the service on the port {port}."
            print(message)
            logger.warning(message)
            kill_exist_service(port)
        else:
            logger.warning(f"Service port {port} is used.")
            raise UserErrorException(f"Service port {port} is used.")


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


def _start_detach_service_in_win(port):
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
        f"waitress-serve --listen=127.0.0.1:{port} --threads={PF_SERVICE_WORKER_NUM} "
        "promptflow._cli._pf._service:get_app"
    )
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


def _start_detach_service_in_unix(port):
    # Set host to localhost, only allow request from localhost.
    cmd = [
        "waitress-serve",
        f"--listen=127.0.0.1:{port}",
        f"--threads={PF_SERVICE_WORKER_NUM}",
        "promptflow._cli._pf._service:get_app",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, start_new_session=True)


def stop_service():
    port = get_port_from_config()
    if port is not None and is_port_in_use(port):
        kill_exist_service(port)
        message = f"Promptflow service stop in {port}."
    else:
        message = "Promptflow service is not started."
    logger.debug(message)
    print(message)


def show_service():
    port = get_port_from_config()
    status = get_started_service_info(port)
    if is_run_from_built_binary():
        log_file = HOME_PROMPT_FLOW_DIR / PF_SERVICE_LOG_FILE
    else:
        log_file = get_current_env_pfs_file(PF_SERVICE_LOG_FILE)
    if status:
        status.update({"log_file": log_file.as_posix()})
        print(status)
        return
    else:
        logger.warning(f"Promptflow service is not started. log_file: {log_file.as_posix()}")
        sys.exit(1)
