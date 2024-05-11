# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential

from promptflow._constants import AzureWorkspaceKind, CosmosDBContainerName
from promptflow._sdk._utilities.general_utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure import PFClient
from promptflow.azure._constants._trace import COSMOS_DB_SETUP_RESOURCE_TYPE
from promptflow.azure._restclient.flow_service_caller import FlowRequestException
from promptflow.exceptions import ErrorTarget, UserErrorException

_logger = get_cli_sdk_logger()


def _create_trace_destination_value_user_error(message: str) -> UserErrorException:
    return UserErrorException(message=message, target=ErrorTarget.CONTROL_PLANE_SDK)


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
    # try to retrieve the token from PFS; if failed, call PFS init API and start polling
    _logger.debug("Validating workspace Cosmos DB is initialized...")
    pf_client = PFClient(ml_client=ml_client)
    try:
        pf_client._traces._get_cosmos_db_token(container_name=CosmosDBContainerName.SPAN)
        _logger.debug("The workspace Cosmos DB is already initialized.")
    except FlowRequestException:
        # print here to let users aware this operation as it's kind of time consuming
        init_cosmos_msg = (
            "The workspace Cosmos DB is not initialized yet, "
            "will start initialization, which may take some minutes..."
        )
        print(init_cosmos_msg)
        _logger.debug(init_cosmos_msg)
        pf_client._traces._setup_cosmos_db(resource_type=COSMOS_DB_SETUP_RESOURCE_TYPE)
    _logger.debug("The workspace Cosmos DB is initialized.")

    _logger.debug("pf.config.trace.destination is valid.")
