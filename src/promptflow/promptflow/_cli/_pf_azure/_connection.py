# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from pathlib import Path

from dotenv import dotenv_values

from promptflow._cli._utils import (
    _set_workspace_argument_for_subparsers,
    get_client_for_cli,
)
from promptflow._sdk._constants import LOGGER_NAME
from promptflow.connections import CustomConnection
from promptflow.contracts.types import Secret

logger = logging.getLogger(LOGGER_NAME)


def add_connection_parser(subparsers):
    connection_parser = subparsers.add_parser(
        "connection",
        description="A CLI tool to manage connections for promptflow.",
        help="pf connection",
    )
    subparsers = connection_parser.add_subparsers()
    add_connection_create(subparsers)
    add_connection_get(subparsers)
    connection_parser.set_defaults(action="connection")


def add_connection_create(subparsers):
    create_parser = subparsers.add_parser(
        "create",
        description="Create a connection for promptflow.",
        help="pf connection create",
    )
    _set_workspace_argument_for_subparsers(create_parser)
    create_parser.add_argument(
        "--name", "-n", type=str, help="Name of the connection to create."
    )
    create_parser.add_argument(
        "--type",
        type=str,
        help='Type of the connection, Possible values include: "OpenAI", "AzureOpenAI", "Serp", "Bing", '
        '"Custom", "AzureContentSafety", "CognitiveSearch", "SubstrateLLM',
    )
    # TODO: reuse existing code
    create_parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="the dotenv file path containing the environment variables to be used in the flow.",
    )
    create_parser.set_defaults(sub_action="create")


def add_connection_get(subparsers):
    get_parser = subparsers.add_parser(
        "get", description="Get a connection for promptflow.", help="pf connection get"
    )
    _set_workspace_argument_for_subparsers(get_parser)
    get_parser.add_argument(
        "--name", "-n", type=str, help="Name of the connection to get."
    )
    get_parser.set_defaults(sub_action="get")


def _get_conn_operations(subscription_id, resource_group, workspace_name):
    from promptflow.azure import PFClient

    client = get_client_for_cli(
        subscription_id=subscription_id,
        workspace_name=workspace_name,
        resource_group_name=resource_group,
    )
    pf = PFClient(client)
    return pf._connections


def create_conn(name, type, env, subscription_id, resource_group, workspace_name):
    from promptflow._sdk.entities._connection import _Connection

    if not Path(env).exists():
        raise ValueError(f"Env file {env} does not exist.")
    try:
        dot_env = dotenv_values(env)
    except Exception as e:
        raise ValueError(f"Failed to load env file {env}. Error: {e}")
    custom_configs = CustomConnection(**{k: Secret(v) for k, v in dot_env.items()})
    connection = _Connection(
        name=name,
        type=type,
        custom_configs=custom_configs,
        connection_scope="WorkspaceShared",
    )

    conn_ops = _get_conn_operations(subscription_id, resource_group, workspace_name)
    result = conn_ops.create_or_update(connection=connection)
    print(result._to_yaml())


def get_conn(name, subscription_id, resource_group, workspace_name):
    conn_ops = _get_conn_operations(subscription_id, resource_group, workspace_name)
    result = conn_ops.get(name=name)
    print(result._to_yaml())
