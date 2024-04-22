# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

from dotenv import dotenv_values

from promptflow._cli._params import add_param_connection_name, add_param_env, base_params
from promptflow._cli._utils import _set_workspace_argument_for_subparsers, activate_action
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure._cli._utils import get_client_for_cli
from promptflow.connections import CustomConnection
from promptflow.contracts.types import Secret

logger = get_cli_sdk_logger()


def add_connection_parser(subparsers):
    connection_parser = subparsers.add_parser(
        "connection", description="A CLI tool to manage connections for promptflow.", help="pf connection"
    )
    subparsers = connection_parser.add_subparsers()
    add_connection_create(subparsers)
    add_connection_get(subparsers)
    connection_parser.set_defaults(action="connection")


def add_connection_create(subparsers):
    add_param_type = lambda parser: parser.add_argument(  # noqa: E731
        "--type",
        type=str,
        help='Type of the connection, Possible values include: "OpenAI", "AzureOpenAI", "Serp", "Bing", '
        '"Custom", "AzureContentSafety", "CognitiveSearch", "SubstrateLLM',
    )
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_connection_name,
        add_param_type,
        add_param_env,
    ] + base_params

    activate_action(
        name="create",
        description="Create a connection for promptflow.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="pf connection create",
        action_param_name="sub_action",
    )


def add_connection_get(subparsers):
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_connection_name,
        add_param_env,
    ] + base_params

    activate_action(
        name="get",
        description="Get a connection for promptflow.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="pf connection get",
        action_param_name="sub_action",
    )


def _get_conn_operations(subscription_id, resource_group, workspace_name):
    from promptflow.azure import PFClient

    client = get_client_for_cli(
        subscription_id=subscription_id, workspace_name=workspace_name, resource_group_name=resource_group
    )
    pf = PFClient(ml_client=client)
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
    connection = _Connection(name=name, type=type, custom_configs=custom_configs, connection_scope="WorkspaceShared")

    conn_ops = _get_conn_operations(subscription_id, resource_group, workspace_name)
    result = conn_ops.create_or_update(connection=connection)
    print(result._to_yaml())


def get_conn(name, subscription_id, resource_group, workspace_name):
    conn_ops = _get_conn_operations(subscription_id, resource_group, workspace_name)
    result = conn_ops.get(name=name)
    print(result._to_yaml())
