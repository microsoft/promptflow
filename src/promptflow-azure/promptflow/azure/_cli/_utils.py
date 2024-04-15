# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os

from promptflow._cli._utils import get_workspace_triad_from_local
from promptflow._sdk._constants import EnvironmentVariables
from promptflow._utils.utils import is_in_ci_pipeline
from promptflow.azure import PFClient
from promptflow.exceptions import ErrorTarget, UserErrorException


class IdentityEnvironmentVariable:
    """This class is copied from mldesigner._constants.IdentityEnvironmentVariable."""

    DEFAULT_IDENTITY_CLIENT_ID = "DEFAULT_IDENTITY_CLIENT_ID"
    OBO_ENABLED_FLAG = "AZUREML_OBO_ENABLED"


def get_client_info_for_cli(subscription_id: str = None, resource_group_name: str = None, workspace_name: str = None):
    if not (subscription_id and resource_group_name and workspace_name):
        workspace_triad = get_workspace_triad_from_local()
        subscription_id = subscription_id or workspace_triad.subscription_id
        resource_group_name = resource_group_name or workspace_triad.resource_group_name
        workspace_name = workspace_name or workspace_triad.workspace_name

    if not (subscription_id and resource_group_name and workspace_name):
        workspace_name = workspace_name or os.getenv("AZUREML_ARM_WORKSPACE_NAME")
        subscription_id = subscription_id or os.getenv("AZUREML_ARM_SUBSCRIPTION")
        resource_group_name = resource_group_name or os.getenv("AZUREML_ARM_RESOURCEGROUP")

    return subscription_id, resource_group_name, workspace_name


def _use_azure_cli_credential():
    return os.environ.get(EnvironmentVariables.PF_USE_AZURE_CLI_CREDENTIAL, "false").lower() == "true"


def get_credentials_for_cli():
    """
    This function is part of mldesigner.dsl._dynamic_executor.DynamicExecutor._get_ml_client with
    some local imports.
    """
    from promptflow._utils.logger_utils import get_cli_sdk_logger

    logger = get_cli_sdk_logger()

    from azure.ai.ml.identity import AzureMLOnBehalfOfCredential
    from azure.identity import AzureCliCredential, DefaultAzureCredential, ManagedIdentityCredential

    # May return a different one if executing in local
    # credential priority: OBO > azure cli > managed identity > default
    # check OBO via environment variable, the referenced code can be found from below search:
    # https://msdata.visualstudio.com/Vienna/_search?text=AZUREML_OBO_ENABLED&type=code&pageSize=25&filters=ProjectFilters%7BVienna%7D&action=contents
    if os.getenv(IdentityEnvironmentVariable.OBO_ENABLED_FLAG):
        logger.debug("User identity is configured, use OBO credential.")
        credential = AzureMLOnBehalfOfCredential()
    elif _use_azure_cli_credential():
        logger.debug("Use azure cli credential since specified in environment variable.")
        credential = AzureCliCredential()
    else:
        client_id_from_env = os.getenv(IdentityEnvironmentVariable.DEFAULT_IDENTITY_CLIENT_ID)
        if client_id_from_env:
            # use managed identity when client id is available from environment variable.
            # reference code:
            # https://learn.microsoft.com/en-us/azure/machine-learning/how-to-identity-based-service-authentication?tabs=cli#compute-cluster
            logger.debug("Use managed identity credential.")
            credential = ManagedIdentityCredential(client_id=client_id_from_env)
        elif is_in_ci_pipeline():
            # use managed identity when executing in CI pipeline.
            logger.debug("Use azure cli credential since in CI pipeline.")
            credential = AzureCliCredential()
        else:
            # use default Azure credential to handle other cases.
            logger.debug("Use default credential.")
            credential = DefaultAzureCredential()

    return credential


def get_client_for_cli(*, subscription_id: str = None, resource_group_name: str = None, workspace_name: str = None):
    from azure.ai.ml import MLClient

    subscription_id, resource_group_name, workspace_name = get_client_info_for_cli(
        subscription_id=subscription_id, resource_group_name=resource_group_name, workspace_name=workspace_name
    )
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


def _get_azure_pf_client(subscription_id=None, resource_group=None, workspace_name=None, debug=False):
    ml_client = get_client_for_cli(
        subscription_id=subscription_id, resource_group_name=resource_group, workspace_name=workspace_name
    )
    client = PFClient(ml_client=ml_client, logging_enable=debug)
    return client
