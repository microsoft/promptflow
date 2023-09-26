# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import importlib
import json
import logging
import os
from functools import partial
from importlib.metadata import version

from ruamel.yaml import YAML
from promptflow._cli._params import add_param_all_results, add_param_max_results, add_param_set, logging_params, \
    add_param_output
from promptflow._cli._utils import activate_action, confirm, exception_handler, get_secret_input, print_yellow_warning
from promptflow._sdk._constants import LOGGER_NAME, MAX_LIST_CLI_RESULTS
from promptflow._sdk._load_functions import load_connection
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._utils import load_yaml
from promptflow._sdk.entities._connection import _Connection
from promptflow._utils.connection_utils import (
    generate_custom_strong_type_connection_template,
    generate_custom_strong_type_connection_spec)

logger = logging.getLogger(LOGGER_NAME)
_client = PFClient()  # Do we have some function like PFClient.get_instance?


def add_param_file(parser):
    parser.add_argument("--file", "-f", type=str, help="File path of the connection yaml.", required=True)


def add_param_name(parser, required=False):
    parser.add_argument("--name", "-n", type=str, help="Name of the connection.", required=required)


def add_param_module(parser, required=False):
    parser.add_argument("--module", "-m", type=str, help="Module of the connection.", required=required)


def add_param_package(parser, required=False):
    parser.add_argument("--package", type=str, help="Custom package name.", required=required)


def add_connection_parser(subparsers):
    connection_parser = subparsers.add_parser(
        "connection",
        description="""A CLI tool to manage connections for promptflow.

        Your secrets will be encrypted using AES(Advanced Encryption Standard) technology.""",  # noqa: E501
        help="pf connection",
    )
    subparsers = connection_parser.add_subparsers()
    add_connection_create(subparsers)
    add_connection_update(subparsers)
    add_connection_show(subparsers)
    add_connection_list(subparsers)
    add_connection_delete(subparsers)
    add_gen_connection_template(subparsers)
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
        add_params=[add_param_max_results, add_param_all_results] + logging_params,
        subparsers=subparsers,
        help_message="List all connections.",
        action_param_name="sub_action",
    )


def add_gen_connection_template(subparsers):
    epilog = """
    Examples:
    # Generate connection template:
    pf connection gen-template -n my_connection_name -m my_module_name --package my_package_name --output ./output
    """
    activate_action(
        name="gen-template",
        description="Generate connection template.",
        epilog=epilog,
        add_params=[partial(add_param_name, required=True),
                    partial(add_param_module, required=True),
                    partial(add_param_package, required=True),
                    add_param_output] + logging_params,
        subparsers=subparsers,
        help_message="Generate connection template.",
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
def list_connection(max_results=MAX_LIST_CLI_RESULTS, all_results=False):
    connections = _client.connections.list(max_results, all_results)
    print(json.dumps([connection._to_dict() for connection in connections], indent=4))


def _upsert_connection_from_file(file, params_override=None):
    # Note: This function is used for pfutil, do not edit it.
    params_override = params_override or []
    params_override.append(load_yaml(file))
    connection = load_connection(source=file, params_override=params_override)
    existing_connection = _client.connections.get(connection.name, raise_error=False)
    if existing_connection:
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


@exception_handler("Generate connection template")
def gen_connection_template(name, module, package, output):
    connection_module = importlib.import_module(module)
    cls = getattr(connection_module, name)
    package_version = version(package)
    spec = generate_custom_strong_type_connection_spec(cls, package, package_version)
    template = generate_custom_strong_type_connection_template(cls, spec, package, package_version)
    file_path = os.path.join(output, "connection_template.yaml")
    if not os.path.exists(output):
        os.makedirs(output)

    with open(file_path, 'w') as file:
        yaml = YAML()
        yaml.dump(yaml.load(template), file)
        print(f"Completed to write the generated connection template to file {file_path}.")


def dispatch_connection_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_connection(args.file, args.params_override, args.name)
    elif args.sub_action == "show":
        show_connection(args.name)
    elif args.sub_action == "list":
        list_connection(args.max_results, args.all_results)
    elif args.sub_action == "update":
        update_connection(args.name, args.params_override)
    elif args.sub_action == "delete":
        delete_connection(args.name)
    elif args.sub_action == "gen-template":
        gen_connection_template(args.name, args.module, args.package, args.output)
