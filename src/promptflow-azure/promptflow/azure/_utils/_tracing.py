# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import typing

from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential

from promptflow._constants import AzureWorkspaceKind
from promptflow._sdk._constants import AzureMLWorkspaceTriad
from promptflow._sdk._utilities.general_utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure import PFClient
from promptflow.azure._constants._trace import COSMOS_DB_SETUP_RESOURCE_TYPE
from promptflow.azure._entities._trace import CosmosMetadata
from promptflow.exceptions import ErrorTarget, UserErrorException

_logger = get_cli_sdk_logger()


def _create_trace_destination_value_user_error(message: str) -> UserErrorException:
    return UserErrorException(message=message, target=ErrorTarget.CONTROL_PLANE_SDK)


def resolve_disable_trace(metadata: CosmosMetadata, logger: typing.Optional[logging.Logger] = None) -> bool:
    """Resolve `disable_trace` from Cosmos DB metadata.

    Only return True when the Cosmos DB is disabled; will log warning if the Cosmos DB is not ready.
    """
    if logger is None:
        logger = _logger
    if metadata.is_disabled():
        logger.debug("the trace cosmos db is disabled.")
        return True
    if not metadata.is_ready():
        warning_message = (
            "The trace Cosmos DB for current workspace/project is not ready yet, "
            "your traces might not be logged and stored properly.\n"
            "To enable it, please run `pf config set trace.destination="
            "azureml://subscriptions/<subscription-id>/"
            "resourceGroups/<resource-group-name>/providers/Microsoft.MachineLearningServices/"
            "workspaces/<workspace-or-project-name>`, prompt flow will help to get everything ready.\n"
        )
        logger.warning(warning_message)
    return False


def is_trace_cosmos_available(ws_triad: AzureMLWorkspaceTriad, logger: typing.Optional[logging.Logger] = None) -> bool:
    if logger is None:
        logger = _logger
    pf_client = PFClient(
        credential=AzureCliCredential(),
        subscription_id=ws_triad.subscription_id,
        resource_group_name=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    )
    cosmos_metadata = pf_client._traces._get_cosmos_metadata()
    return not resolve_disable_trace(metadata=cosmos_metadata, logger=logger)


def validate_trace_destination(value: str) -> None:
    """Validate pf.config.trace.destination.

    1. the value is a valid ARM resource ID for workspace/project
    2. the resource exists
    3. the resource is an Azure ML workspace or AI project
    4. the workspace Cosmos DB is initialized
    """
    # valid workspace/project ARM resource ID; otherwise, a ValueError will be raised
    _logger.debug("Validating pf.config.trace.destination...")
    try:
        workspace_triad = extract_workspace_triad_from_trace_provider(value)
    except ValueError as e:
        raise _create_trace_destination_value_user_error(str(e))

    # the resource exists
    _logger.debug("Validating resource exists...")
    ml_client = MLClient(
        credential=AzureCliCredential(),  # this validation only happens in CLI, so use CLI credential
        subscription_id=workspace_triad.subscription_id,
        resource_group_name=workspace_triad.resource_group_name,
        workspace_name=workspace_triad.workspace_name,
    )
    try:
        workspace = ml_client.workspaces.get(name=workspace_triad.workspace_name)
    except ResourceNotFoundError as e:
        raise _create_trace_destination_value_user_error(str(e))
    _logger.debug("Resource exists.")

    # Azure ML workspace or AI project
    _logger.debug("Validating resource type...")
    if AzureWorkspaceKind.is_hub(workspace):
        error_msg = (
            f"{workspace.name!r} is an Azure AI hub, which is not a valid type. "
            "Currently we support Azure ML workspace and AI project as trace provider."
        )
        raise _create_trace_destination_value_user_error(error_msg)
    _logger.debug("Resource type is valid.")

    # the workspace Cosmos DB is initialized
    # if not, call PFS setup API and start polling
    _logger.debug("Validating workspace Cosmos DB is initialized...")
    pf_client = PFClient(ml_client=ml_client)
    cosmos_metadata = pf_client._traces._get_cosmos_metadata()
    # raise error if the Cosmos DB is disabled
    if cosmos_metadata.is_disabled():
        error_message = "The workspace Cosmos DB is disabled, please enable it first."
        _logger.error(error_message)
        raise _create_trace_destination_value_user_error(error_message)
    if not cosmos_metadata.is_ready():
        # print here to let users aware this operation as it's kind of time consuming
        init_cosmos_msg = (
            "The workspace Cosmos DB is not initialized yet, "
            "will start initialization, which may take some minutes..."
        )
        print(init_cosmos_msg)
        _logger.debug(init_cosmos_msg)
        pf_client._traces._setup_cosmos_db(resource_type=COSMOS_DB_SETUP_RESOURCE_TYPE)
    else:
        _logger.debug("The workspace Cosmos DB is available.")
    _logger.debug("The workspace Cosmos DB is initialized.")

    _logger.debug("pf.config.trace.destination is valid.")
