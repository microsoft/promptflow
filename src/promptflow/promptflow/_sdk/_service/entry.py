# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json
import logging
import os
import platform
import subprocess
import sys

import waitress

from promptflow._cli._utils import _get_cli_activity_name, cli_exception_and_telemetry_handler
from promptflow._constants import PF_NO_INTERACTIVE_LOGIN
from promptflow._sdk._constants import LOGGER_NAME, PF_SERVICE_DEBUG
from promptflow._sdk._service.app import create_app
from promptflow._sdk._service.utils.utils import (
    check_pfs_service_status,
    dump_port_to_config,
    get_port_from_config,
    get_started_service_info,
    is_port_in_use,
    kill_deprecated_service,
    kill_exist_service,
)
from promptflow._sdk._utils import get_promptflow_sdk_version, print_pf_version
from promptflow.exceptions import UserErrorException

app, _ = create_app()


def get_app(environ, start_response):
    app, _ = create_app()
    if os.environ.get(PF_SERVICE_DEBUG) == "true":
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
    return app.wsgi_app(environ, start_response)


def add_start_service_action(subparsers):
    """Add action to start pfs."""
    start_pfs_parser = subparsers.add_parser(
        "start",
        description="Start promptflow service.",
        help="pfs start",
    )
    start_pfs_parser.add_argument("-p", "--port", type=int, help="port of the promptflow service")
    start_pfs_parser.add_argument(
        "--force",
        action="store_true",
        help="If the port is used, the existing service will be terminated and restart a new service.",
    )
    start_pfs_parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="The flag to turn on debug mode for pfs.",
    )
    start_pfs_parser.set_defaults(action="start")


def add_stop_service_action(subparsers):
    """Add action to stop pfs."""
    stop_pfs_parser = subparsers.add_parser(
        "stop",
        description="Stop promptflow service.",
        help="pfs stop",
    )
    stop_pfs_parser.set_defaults(action="stop")


def add_show_status_action(subparsers):
    """Add action to show pfs status."""
    show_status_parser = subparsers.add_parser(
        "show-status",
        description="Display the started promptflow service info.",
        help="pfs show-status",
    )
    show_status_parser.set_defaults(action="show-status")


def start_service(args):
    # User Agent will be set based on header in request, so not set globally here.
    os.environ[PF_NO_INTERACTIVE_LOGIN] = "true"
    port = args.port
    if args.debug:
        os.environ[PF_SERVICE_DEBUG] = "true"
        app.logger.setLevel(logging.DEBUG)

    # add this logic to stop pfs service which is start in the port of service key
    kill_deprecated_service()

    def validate_port(port, force_start):
        if is_port_in_use(port):
            if force_start:
                app.logger.warning(f"Force restart the service on the port {port}.")
                kill_exist_service(port)
            else:
                app.logger.warning(f"Service port {port} is used.")
                raise UserErrorException(f"Service port {port} is used.")

    if port:
        dump_port_to_config(port)
        validate_port(port, args.force)
    else:
        port = get_port_from_config(create_if_not_exists=True)
        validate_port(port, args.force)

    if sys.executable.endswith("pfcli.exe"):
        # For msi installer, use sdk api to start pfs since it's not supported to invoke waitress by cli directly
        # after packaged by Pyinstaller.
        app.logger.info(
            f"Start Prompt Flow Service on http://localhost:{port}, version: {get_promptflow_sdk_version()}"
        )
        waitress.serve(app, host="127.0.0.1", port=port)
    else:
        # Note: in this scenario, we will have two app, one is the parent process created to log, one is created in
        # the detached child process.
        # Set host to localhost, only allow request from localhost.
        cmd = ["waitress-serve", f"--listen=127.0.0.1:{port}", "promptflow._sdk._service.entry:get_app"]
        # Start a pfs process using detach mode. It will start a new process and create a new app. So we use environment
        # variable to pass the debug mode, since it will inherit parent process environment variable.
        if platform.system() == "Windows":
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        is_healthy = check_pfs_service_status(port)
        if is_healthy:
            app.logger.info(
                f"Start Prompt Flow Service on http://localhost:{port}, version: {get_promptflow_sdk_version()}"
            )
        else:
            app.logger.warning(f"Pfs service start failed in {port}.")


def stop_service():
    port = get_port_from_config()
    if port is not None:
        kill_exist_service(port)
        app.logger.info(f"Pfs service stop in {port}.")


def main():
    command_args = sys.argv[1:]
    if len(command_args) == 1 and command_args[0] == "version":
        version_dict = {"promptflow": get_promptflow_sdk_version()}
        return json.dumps(version_dict, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    if len(command_args) == 0:
        command_args.append("-h")
    entry(command_args)


def entry(command_args):
    parser = argparse.ArgumentParser(
        prog="pfs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Prompt Flow Service",
    )

    parser.add_argument(
        "-v", "--version", dest="version", action="store_true", help="show current PromptflowService version and exit"
    )
    subparsers = parser.add_subparsers()
    add_start_service_action(subparsers)
    add_show_status_action(subparsers)
    add_stop_service_action(subparsers)

    args = parser.parse_args(command_args)

    activity_name = _get_cli_activity_name(cli=parser.prog, args=args)
    cli_exception_and_telemetry_handler(run_command, activity_name)(args)


def run_command(args):
    if args.version:
        print_pf_version()
        return
    elif args.action == "show-status":
        port = get_port_from_config()
        status = get_started_service_info(port)
        if status:
            print(status)
            return
        else:
            logger = logging.getLogger(LOGGER_NAME)
            logger.warning("Promptflow service is not started.")
            exit(1)
    elif args.action == "start":
        start_service(args)
    elif args.action == "stop":
        stop_service()


if __name__ == "__main__":
    main()
