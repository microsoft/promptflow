# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import contextlib
import json
import logging
import os
import sys
import traceback
from collections import namedtuple
from configparser import ConfigParser
from getpass import getpass
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

from promptflow.exceptions import ErrorTarget, UserErrorException
from promptflow.utils.utils import is_in_ci_pipeline

AzureMLWorkspaceTriad = namedtuple("AzureMLWorkspace", ["subscription_id", "resource_group_name", "workspace_name"])

logger = logging.getLogger(__name__)


def _set_workspace_argument_for_subparsers(subparser, required=False):
    """Add workspace arguments to subparsers."""
    # Make these arguments optional so that user can use local azure cli context
    subparser.add_argument(
        "--subscription", required=required, type=str, help="Subscription id, required when pass run id."
    )
    subparser.add_argument(
        "--resource-group", "-g", required=required, type=str, help="Resource group name, required when pass run id."
    )
    subparser.add_argument(
        "--workspace-name", "-w", required=required, type=str, help="Workspace name, required when pass run id."
    )


def dump_connection_file(dot_env_file: str):
    for key in ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_BASE", "CHAT_DEPLOYMENT_NAME"]:
        if key not in os.environ:
            # skip dump connection file if not all required environment variables are set
            return

    connection_file_path = "./connection.json"
    os.environ["PROMPTFLOW_CONNECTIONS"] = connection_file_path

    load_dotenv(dot_env_file)
    connection_dict = {
        "custom_connection": {
            "type": "CustomConnection",
            "value": {
                "AZURE_OPENAI_API_KEY": os.environ["AZURE_OPENAI_API_KEY"],
                "AZURE_OPENAI_API_BASE": os.environ["AZURE_OPENAI_API_BASE"],
                "CHAT_DEPLOYMENT_NAME": os.environ["CHAT_DEPLOYMENT_NAME"],
            },
            "module": "promptflow.connections",
        }
    }
    with open(connection_file_path, "w") as f:
        json.dump(connection_dict, f)


def get_workspace_triad_from_local() -> AzureMLWorkspaceTriad:
    subscription_id = None
    resource_group_name = None
    workspace_name = None
    azure_config_path = Path.home() / ".azure"
    config_parser = ConfigParser()
    # subscription id
    try:
        config_parser.read_file(open(azure_config_path / "clouds.config"))
        subscription_id = config_parser["AzureCloud"]["subscription"]
    except Exception:  # pylint: disable=broad-except
        pass
    # resource group name & workspace name
    try:
        config_parser.read_file(open(azure_config_path / "config"))
        resource_group_name = config_parser["defaults"]["group"]
        workspace_name = config_parser["defaults"]["workspace"]
    except Exception:  # pylint: disable=broad-except
        pass

    return AzureMLWorkspaceTriad(subscription_id, resource_group_name, workspace_name)


def get_credentials_for_cli():
    """
    This function is part of mldesigner.dsl._dynamic_executor.DynamicExecutor._get_ml_client with
    some local imports.
    """
    from azure.ai.ml.identity import AzureMLOnBehalfOfCredential
    from azure.identity import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential

    # May return a different one if executing in local
    # credential priority: OBO > managed identity > default
    # check OBO via environment variable, the referenced code can be found from below search:
    # https://msdata.visualstudio.com/Vienna/_search?text=AZUREML_OBO_ENABLED&type=code&pageSize=25&filters=ProjectFilters%7BVienna%7D&action=contents
    if os.getenv(IdentityEnvironmentVariable.OBO_ENABLED_FLAG):
        logger.info("User identity is configured, use OBO credential.")
        credential = AzureMLOnBehalfOfCredential()
    else:
        client_id_from_env = os.getenv(IdentityEnvironmentVariable.DEFAULT_IDENTITY_CLIENT_ID)
        if client_id_from_env:
            # use managed identity when client id is available from environment variable.
            # reference code:
            # https://learn.microsoft.com/en-us/azure/machine-learning/how-to-identity-based-service-authentication?tabs=cli#compute-cluster
            logger.info("Use managed identity credential.")
            credential = ManagedIdentityCredential(client_id=client_id_from_env)
        elif is_in_ci_pipeline():
            # use managed identity when executing in CI pipeline.
            logger.info("Use azure cli credential.")
            credential = AzureCliCredential()
        else:
            # use default Azure credential to handle other cases.
            logger.info("Use default credential.")
            credential = DefaultAzureCredential()

    return credential


def get_client_for_cli(*, subscription_id: str = None, resource_group_name: str = None, workspace_name: str = None):
    from azure.ai.ml import MLClient
    from knack.util import CLIError

    if not (subscription_id and resource_group_name and workspace_name):
        try:
            workspace_triad = get_workspace_triad_from_local()
            subscription_id = subscription_id or workspace_triad.subscription_id
            resource_group_name = resource_group_name or workspace_triad.resource_group_name
            workspace_name = workspace_name or workspace_triad.workspace_name
        except CLIError as e:
            logger.info("Failed to get workspace triad from CLI context, fallback to use default credential: %s", e)

    if not (subscription_id and resource_group_name and workspace_name):
        workspace_name = workspace_name or os.getenv("AZUREML_ARM_WORKSPACE_NAME")
        subscription_id = subscription_id or os.getenv("AZUREML_ARM_SUBSCRIPTION")
        resource_group_name = resource_group_name or os.getenv("AZUREML_ARM_RESOURCEGROUP")

    missing_fields = []
    for key in ["workspace_name", "subscription_id", "resource_group_name"]:
        if not locals()[key]:
            missing_fields.append(key)
    if missing_fields:
        raise UserErrorException(
            "Please provide all required fields to work on specific workspace: {}".format(", ".join(missing_fields)),
            target=ErrorTarget.CONTROL_PLANE_SDK,
        )

    return MLClient(
        credential=get_credentials_for_cli(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )


def confirm(question) -> bool:
    answer = input(f"{question} [y/n]")
    while answer.lower() not in ["y", "n"]:
        answer = input("Please input 'y' or 'n':")
    return answer.lower() == "y"


@contextlib.contextmanager
def inject_sys_path(path):
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path = original_sys_path


def activate_action(name, description, epilog, add_params, subparsers, action_param_name="action"):
    parser = subparsers.add_parser(
        name,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=description,
    )
    if add_params:
        for add_param_func in add_params:
            add_param_func(parser)
    parser.set_defaults(**{action_param_name: name})
    return parser


class IdentityEnvironmentVariable:
    """This class is copied from mldesigner._constants.IdentityEnvironmentVariable."""

    DEFAULT_IDENTITY_CLIENT_ID = "DEFAULT_IDENTITY_CLIENT_ID"
    OBO_ENABLED_FLAG = "AZUREML_OBO_ENABLED"


def _dump_entity_with_warnings(entity) -> Dict:
    if not entity:
        return
    if isinstance(entity, Dict):
        return entity
    try:
        return entity._to_dict()  # type: ignore
    except Exception as err:
        logger.warning("Failed to deserialize response: " + str(err))
        logger.warning(str(entity))
        logger.debug(traceback.format_exc())


def get_migration_secret_from_args(args, *, raise_errors=True, allow_input=True):
    if args.migration_secret:
        return args.migration_secret
    if args.migration_secret_file:
        if not os.path.exists(args.migration_secret_file):
            if raise_errors:
                raise UserErrorException(f"Migration secret file {args.migration_secret_file} does not exist.")
            else:
                return None
        return Path(args.migration_secret_file).read_text()
    if allow_input:
        migration_secret = getpass("Please input a migration secret:")
        return migration_secret
    if raise_errors:
        raise UserErrorException(
            "Please provide an migration secret via `--migration-secret` or `--migration-secret-file`."
        )
    return None


def list_of_dict_to_dict(obj: list):
    if not isinstance(obj, list):
        return {}
    result = {}
    for item in obj:
        result.update(item)
    return result


def _get_promptflow_version():
    import promptflow

    try:
        return promptflow.__version__
    except AttributeError:
        # if promptflow is installed from source, it does not have __version__ attribute
        return "0.0.1"
