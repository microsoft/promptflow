# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json
from functools import partial

from promptflow._cli._params import add_param_set
from promptflow._cli.pf_logger_factory import _LoggerFactory
from promptflow._cli.utils import activate_action, confirm
from promptflow.sdk._load_functions import load_connection
from promptflow.sdk._pf_client import PFClient
from promptflow.sdk.entities._connection import _Connection

logger = _LoggerFactory.get_logger()
_client = PFClient()  # Do we have some function like PFClient.get_instance?


def add_param_file(parser):
    parser.add_argument("--file", "-f", type=str, help="File path of the connection yaml.", required=True)


def add_param_name(parser, required=False):
    parser.add_argument("--name", "-n", type=str, help="Name of the connection.", required=required)


def add_connection_parser(subparsers):
    connection_parser = subparsers.add_parser(
        "connection", description="A CLI tool to manage connections for promptflow.", help="pf connection"
    )
    subparsers = connection_parser.add_subparsers()
    add_connection_create(subparsers)
    add_connection_update(subparsers)
    add_connection_show(subparsers)
    add_connection_list(subparsers)
    add_connection_delete(subparsers)
    connection_parser.set_defaults(action="connection")


def add_connection_create(subparsers):
    epilog = """
Examples:

# Creating a connection with yaml file:
pf connection create -f connection.yaml
# Creating a connection with yaml file and overrides:
pf connection create -f connection.yaml --set api_key="my_api_key"
# Creating a custom connection with .env file, note that overrides specified by --set will be ignored:
pf connection create -f .env --name custom
"""
    activate_action(
        name="create",
        description="Create a connection.",
        epilog=epilog,
        add_params=[add_param_set, add_param_file, add_param_name],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def add_connection_update(subparsers):
    epilog = """
Examples:

# Updating a connection:
pf connection update -n my_connection --set api_key="my_api_key"
"""
    activate_action(
        name="update",
        description="Update a connection.",
        epilog=epilog,
        add_params=[add_param_set, partial(add_param_name, required=True)],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def add_connection_show(subparsers):
    epilog = """
Examples:

# Get and show a connection:
pf connection show -n my_connection_name
"""
    activate_action(
        name="show",
        description="Show a connection for promptflow.",
        epilog=epilog,
        add_params=[partial(add_param_name, required=True)],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def add_connection_delete(subparsers):
    epilog = """
Examples:

# Delete a connection:
pf connection delete -n my_connection_name
"""
    activate_action(
        name="delete",
        description="Delete a connection with specific name.",
        epilog=epilog,
        add_params=[partial(add_param_name, required=True)],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def add_connection_list(subparsers):
    epilog = """
Examples:

# List all connections:
pf connection list
"""
    activate_action(
        name="list",
        description="List all connections.",
        epilog=epilog,
        add_params=[],
        subparsers=subparsers,
        action_param_name="sub_action",
    )


def create_connection(file_path, params_override=None, name=None):
    params_override = params_override or []
    if name:
        params_override.append({"name": name})
    connection = load_connection(source=file_path, params_override=params_override)
    existing_connection = _client.connections.get(connection.name, raise_error=False)
    if existing_connection:
        logger.warning(f"Connection with name {connection.name} already exists. Updating it.")
    connection = _client.connections.create_or_update(connection)
    print(json.dumps(connection._to_dict(), indent=4))


def show_connection(name):
    connection = _client.connections.get(name)
    print(json.dumps(connection._to_dict(), indent=4))


def list_connection():
    connections = _client.connections.list()
    print(json.dumps([connection._to_dict() for connection in connections], indent=4))


def update_connection(name, params_override=None):
    params_override = params_override or []
    existing_connection = _client.connections.get(name, with_secrets=True)
    connection = _Connection._load(data=existing_connection._to_dict(), params_override=params_override)
    connection = _client.connections.create_or_update(connection)
    print(json.dumps(connection._to_dict(), indent=4))


def delete_connection(name):
    if confirm("Are you sure you want to perform this operation?"):
        _client.connections.delete(name)
    else:
        print("The delete operation was canceled.")


def dispatch_connection_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_connection(args.file, args.params_override, args.name)
    elif args.sub_action == "show":
        show_connection(args.name)
    elif args.sub_action == "list":
        list_connection()
    elif args.sub_action == "update":
        update_connection(args.name, args.params_override)
    elif args.sub_action == "delete":
        delete_connection(args.name)
