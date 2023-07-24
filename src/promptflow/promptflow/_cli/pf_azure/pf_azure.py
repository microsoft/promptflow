# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import sys

from promptflow._cli.pf_azure.pf_run import add_parser_run, dispatch_run_commands
from promptflow._cli.utils import _get_promptflow_version


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
        print(_get_promptflow_version())
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
