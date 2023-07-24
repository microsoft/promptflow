# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import sys

from promptflow._cli.pf_connection import add_connection_parser, dispatch_connection_commands
from promptflow._cli.pf_local_flow import add_flow_parser, dispatch_flow_commands
from promptflow._cli.pf_logger_factory import _LoggerFactory
from promptflow._cli.pf_run import add_run_parser, dispatch_run_commands
from promptflow.exceptions import PromptflowException, UserErrorException

from .utils import _get_promptflow_version, get_client_for_cli

logger = _LoggerFactory.get_logger()


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
        "-v", "--version", dest="version", action="store_true", help="show current CLI version and exit"
    )

    subparsers = parser.add_subparsers()
    add_flow_parser(subparsers)
    add_connection_parser(subparsers)
    add_run_parser(subparsers)

    args = parser.parse_args(argv)

    if args.version:
        print(_get_promptflow_version())
    elif args.action == "flow":
        dispatch_flow_commands(args)
    elif args.action == "connection":
        dispatch_connection_commands(args)
    elif args.action == "run":
        dispatch_run_commands(args)


def _get_connections(flow, *, subscription_id=None, resource_group_name=None, workspace_name=None):
    try:
        from azure.core.exceptions import ClientAuthenticationError

        try:
            ml_client = get_client_for_cli(
                subscription_id=subscription_id, resource_group_name=resource_group_name, workspace_name=workspace_name
            )
        except UserErrorException:
            # no enough workspace info, happens when user wants to run flow locally so no log
            return {}

        try:
            # TODO: refactor this after Brynn finished the new interface to get connections
            executable = flow._init_executable()
            connection_names = executable.get_connection_names()
            from promptflow.runtime.connections import build_connection_dict

            return build_connection_dict(
                connection_names=connection_names,
                credential=ml_client._credential,
                subscription_id=ml_client.subscription_id,
                resource_group=ml_client.resource_group_name,
                workspace_name=ml_client.workspace_name,
            )
        except ClientAuthenticationError as e:
            # get_token failure
            logger.info(f"Failed to get token: {e}")
        except PromptflowException as e:
            # PromptflowException for no access to connection, workspace not found, and so on
            logger.info(f"Failed to get connections from workspace: {e}")
            return {}
    except ImportError:
        # dependencies not installed, happens when user wants to run flow locally so no log
        return {}


def main():
    """Entrance of pf CLI."""
    command_args = sys.argv[1:]
    if len(command_args) == 0:
        command_args.append("-h")
    entry(command_args)


if __name__ == "__main__":
    main()
