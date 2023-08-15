# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import sys

from promptflow._cli._pf_azure._run import add_parser_run, dispatch_run_commands
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import get_promptflow_sdk_version

# configure logger for CLI
logger = LoggerFactory.get_logger(name=LOGGER_NAME)


def entry(argv):
    """
    Control plane CLI tools for promptflow cloud version.
    """
    parser = argparse.ArgumentParser(
        prog="pfazure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="PromptFlow CLI cloud version. [Preview]",
    )
    parser.add_argument(
        "-v", "--version", dest="version", action="store_true", help="show current CLI version and exit"
    )

    # flow command is in holding status, may expose in future
    # add_parser_flow(subparsers)

    subparsers = parser.add_subparsers()
    add_parser_run(subparsers)

    args = parser.parse_args(argv)
    if args.version:
        print(get_promptflow_sdk_version())
    elif args.action == "run":
        dispatch_run_commands(args)


def main():
    """Entrance of pf CLI."""
    command_args = sys.argv[1:]
    if len(command_args) == 0:
        command_args.append("-h")
    entry(command_args)


if __name__ == "__main__":
    main()
