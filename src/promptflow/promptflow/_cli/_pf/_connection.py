# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
import logging
from functools import partial

from promptflow._cli._params import add_param_set, logging_params
from promptflow._cli._utils import activate_action, confirm, exception_handler, print_yellow_warning, get_secret_input
from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._load_functions import load_connection
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._utils import load_yaml
from promptflow._sdk.entities._connection import _Connection, CustomConnection

logger = logging.getLogger(LOGGER_NAME)
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
        add_params=[add_param_set, add_param_file, add_param_name] + logging_params,
        subparsers=subparsers,
        help_message="Create a connection.",
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
        add_params=[add_param_set, partial(add_param_name, required=True)] + logging_params,
        subparsers=subparsers,
        help_message="Update a connection.",
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
        add_params=[partial(add_param_name, required=True)] + logging_params,
        subparsers=subparsers,
        help_message="Show a connection for promptflow.",
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
        add_params=[partial(add_param_name, required=True)] + logging_params,
        subparsers=subparsers,
        help_message="Delete a connection with specific name.",
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
        add_params=logging_params,
        subparsers=subparsers,
        help_message="List all connections.",
        action_param_name="sub_action",
    )


def validate_and_interactive_get_secrets(connection, is_update=False):
    """Validate the connection and interactive get secrets if no secrets is provided."""
    prompt = "=================== Please input required secrets ==================="
    missing_secrets_prompt = False
    for name, val in connection.secrets.items():
        if not _Connection._is_scrubbed_value(val) and not _Connection._is_user_input_value(val):
            # Not scrubbed value, not require user input.
            continue
        if is_update and _Connection._is_scrubbed_value(val):
            # Scrubbed value, will use existing, not require user input.
            continue
        if not missing_secrets_prompt:
            print(prompt)
            missing_secrets_prompt = True
        while True:
            secret = get_secret_input(prompt=f"{name}: ")
            if secret:
                break
            print_yellow_warning("Secret can't be empty.")
        connection.secrets[name] = secret
    if missing_secrets_prompt:
        print("=================== Required secrets collected ===================")
    return connection


# Note the connection secrets value behaviors:
# --------------------------------------------------------------------------------
# | secret value     | CLI create   | CLI update          | SDK create_or_update |
# --------------------------------------------------------------------------------
# | empty or all "*" | prompt input | use existing values | use existing values  |
# | <no-change>      | prompt input | use existing values | use existing values  |
# | <user-input>     | prompt input | prompt input        | raise error          |
# --------------------------------------------------------------------------------
@exception_handler("Connection create")
def create_connection(file_path, params_override=None, name=None):
    params_override = params_override or []
    if name:
        params_override.append({"name": name})
    connection = load_connection(source=file_path, params_override=params_override)
    existing_connection = _client.connections.get(connection.name, raise_error=False)
    if existing_connection:
        logger.warning(f"Connection with name {connection.name} already exists. Updating it.")
        # Note: We don't set the existing secret back here, let user input the secrets.
    validate_and_interactive_get_secrets(connection)
    connection = _client.connections.create_or_update(connection)
    print(json.dumps(connection._to_dict(), indent=4))


@exception_handler("Connection show")
def show_connection(name):
    connection = _client.connections.get(name)
    print(json.dumps(connection._to_dict(), indent=4))


@exception_handler("Connection list")
def list_connection():
    connections = _client.connections.list()
    print(json.dumps([connection._to_dict() for connection in connections], indent=4))


def _check_custom_connection_type_match(old_connection, new_connection):
    if type(old_connection) != CustomConnection:
        return

    if type(new_connection) != CustomConnection:
        raise Exception("Connection type mismatch. Please specify the type as 'custom' in the yaml file.")

    if old_connection.is_custom_strong_type():
        if not new_connection.is_custom_strong_type():
            raise Exception(f"Connection custom_type mismatch. Please specify custom_type as {old_connection.custom_type} in the yaml file.")
        elif old_connection.custom_type != new_connection.custom_type:
            raise Exception(f"Connection custom_type mismatch. Existing: {new_connection.custom_type}, supported: {old_connection.custom_type}.")
    # shall we allow custom type to custom strong type?
    elif new_connection.is_custom_strong_type():
        raise Exception(f"....")


def _upsert_connection_from_file(file, params_override=None, connection_spec = None):
    # Note: This function is used for pfutil, do not edit it.
    params_override = params_override or []
    params_override.append(load_yaml(file))
    connection = load_connection(source=file, params_override=params_override, connection_spec=connection_spec)
    existing_connection = _client.connections.get(connection.name, raise_error=False)
    if existing_connection:
        _check_custom_connection_type_match(existing_connection, connection)
        connection = _Connection._load(data=existing_connection._to_dict(), params_override=params_override)
        validate_and_interactive_get_secrets(connection, is_update=True)
        # Set the secrets not scrubbed, as _to_dict() dump scrubbed connections.
        connection._secrets = existing_connection._secrets
    else:
        validate_and_interactive_get_secrets(connection)
    connection = _client.connections.create_or_update(connection)
    return connection


@exception_handler("Connection update")
def update_connection(name, params_override=None):
    params_override = params_override or []
    existing_connection = _client.connections.get(name)
    connection = _Connection._load(data=existing_connection._to_dict(), params_override=params_override)
    validate_and_interactive_get_secrets(connection, is_update=True)
    # Set the secrets not scrubbed, as _to_dict() dump scrubbed connections.
    connection._secrets = existing_connection._secrets
    connection = _client.connections.create_or_update(connection)
    print(json.dumps(connection._to_dict(), indent=4))


@exception_handler("Connection delete")
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
