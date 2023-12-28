# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json
import logging
import os
import sys

import waitress

from promptflow._cli._utils import _get_cli_activity_name
from promptflow._constants import PF_NO_INTERACTIVE_LOGIN
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._service.app import create_app
from promptflow._sdk._service.utils.utils import (
    get_port_from_config,
    get_started_service_info,
    is_port_in_use,
    kill_exist_service,
)
from promptflow._sdk._telemetry import ActivityType, get_telemetry_logger, log_activity
from promptflow._sdk._utils import get_promptflow_sdk_version, print_pf_version
from promptflow._version import VERSION
from promptflow.exceptions import UserErrorException


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
    start_pfs_parser.set_defaults(action="start")


def add_show_status_action(subparsers):
    """Add action to show pfs status."""
    show_status_parser = subparsers.add_parser(
        "show-status",
        description="Display the started promptflow service info.",
        help="pfs show-status",
    )
    show_status_parser.set_defaults(action="show-status")


def start_service(args):
    port = args.port
    app, _ = create_app()
    if port and is_port_in_use(port):
        app.logger.warning(f"Service port {port} is used.")
        raise UserErrorException(f"Service port {port} is used.")
    if not port:
        port = get_port_from_config(create_if_not_exists=True)

    if is_port_in_use(port):
        if args.force:
            app.logger.warning(f"Force restart the service on the port {port}.")
            kill_exist_service(port)
        else:
            app.logger.warning(f"Service port {port} is used.")
            raise UserErrorException(f"Service port {port} is used.")
    # Set host to localhost, only allow request from localhost.
    app.logger.info(f"Start Prompt Flow Service on http://localhost:{port}, version: {get_promptflow_sdk_version()}")
    waitress.serve(app, host="127.0.0.1", port=port)


def main():
    command_args = sys.argv[1:]
    if len(command_args) == 1 and command_args[0] == "version":
        version_dict = {"promptflow": get_promptflow_sdk_version()}
        return json.dumps(version_dict, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    if len(command_args) == 0:
        command_args.append("-h")

    if "USER_AGENT" in os.environ:
        user_agent = f"{os.environ['USER_AGENT']} local_pfs/{VERSION}"
    else:
        user_agent = f"local_pfs/{VERSION}"
    os.environ["USER_AGENT"] = user_agent
    os.environ[PF_NO_INTERACTIVE_LOGIN] = "true"
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

    args = parser.parse_args(command_args)

    activity_name = _get_cli_activity_name(cli=parser.prog, args=args)
    logger = get_telemetry_logger()

    with log_activity(logger, activity_name, activity_type=ActivityType.INTERNALCALL):
        run_command(args)


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


if __name__ == "__main__":
    main()
