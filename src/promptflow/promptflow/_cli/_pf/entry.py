# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import os
import sys

from promptflow._cli._pf._connection import (
    add_connection_parser,
    dispatch_connection_commands,
)
from promptflow._cli._pf._flow import add_flow_parser, dispatch_flow_commands
from promptflow._cli._pf._run import add_run_parser, dispatch_run_commands
from promptflow._cli._user_agent import USER_AGENT
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import get_promptflow_sdk_version

# configure logger for CLI
logger = LoggerFactory.get_logger(name=LOGGER_NAME)


def entry(argv):
    """
    Control plane CLI tools for promptflow.
    """
    parser = argparse.ArgumentParser(
        prog="pf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="PromptFlow CLI. [Preview]",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version",
        action="store_true",
        help="show current CLI version and exit",
    )

    subparsers = parser.add_subparsers()
    add_flow_parser(subparsers)
    add_connection_parser(subparsers)
    add_run_parser(subparsers)

    args = parser.parse_args(argv)

    if args.version:
        print(get_promptflow_sdk_version())
    elif args.action == "flow":
        dispatch_flow_commands(args)
    elif args.action == "connection":
        dispatch_connection_commands(args)
    elif args.action == "run":
        dispatch_run_commands(args)


def setup_user_agent():
    from promptflow._core.operation_context import OperationContext

    if "USER_AGENT" in os.environ:
        # Append vscode user agent
        OperationContext.get_instance().append_user_agent(os.environ["USER_AGENT"])
    # Append CLI user agent
    OperationContext.get_instance().append_user_agent(USER_AGENT)
    logger.debug(
        f"Update the user agent to {OperationContext.get_instance().get_user_agent()}"
    )


def main():
    """Entrance of pf CLI."""
    command_args = sys.argv[1:]
    if len(command_args) == 0:
        command_args.append("-h")
    setup_user_agent()
    entry(command_args)


if __name__ == "__main__":
    main()
