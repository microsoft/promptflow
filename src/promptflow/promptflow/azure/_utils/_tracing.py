# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential, DefaultAzureCredential

from promptflow._constants import CosmosDBContainerName
from promptflow._sdk._tracing import get_ws_tracing_base_url
from promptflow._sdk._utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure import PFClient
from promptflow.azure._restclient.flow_service_caller import FlowRequestException
from promptflow.exceptions import ErrorTarget, UserErrorException

_logger = get_cli_sdk_logger()


def _get_credential() -> typing.Union[AzureCliCredential, DefaultAzureCredential]:
    try:
        credential = AzureCliCredential()
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception:
        return DefaultAzureCredential()


def _create_trace_provider_value_user_error(
    message: str, no_personal_data_message: typing.Optional[str] = None
) -> UserErrorException:
    return UserErrorException(
        message=message,
        target=ErrorTarget.CONTROL_PLANE_SDK,
        no_personal_data_message=no_personal_data_message,
    )


def validate_trace_provider(value: str) -> None:
    """Validate `trace.provider` in pf config.

    1. the value is a valid ARM resource ID for Azure ML workspace
    2. the workspace exists
    3. the workspace Cosmos DB is initialized
    """
    # valid Azure ML workspace ARM resource ID; otherwise, a ValueError will be raised
    try:
        workspace_triad = extract_workspace_triad_from_trace_provider(value)
    except ValueError as e:
        no_personal_data_msg = (
            "Malformed trace provider string, expected azureml://subscriptions/<subscription_id>/"
            "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
            "workspaces/<workspace_name>"
        )
        raise _create_trace_provider_value_user_error(str(e), no_personal_data_msg)

    # the workspace exists
    ml_client = MLClient(
        credential=_get_credential(),
        subscription_id=workspace_triad.subscription_id,
        resource_group_name=workspace_triad.resource_group_name,
        workspace_name=workspace_triad.workspace_name,
    )
    try:
        ml_client.workspaces.get(name=workspace_triad.workspace_name)
    except ResourceNotFoundError as e:
        no_personal_data_msg = "The workspace resource was not found."
        raise _create_trace_provider_value_user_error(str(e), no_personal_data_msg)

    # the workspace Cosmos DB is initialized
    # call PFS API to try to retrieve the token
    # otherwise, print the trace ui and hint the user to init the Cosmos DB from Azure portal
    pf_client = PFClient(ml_client=ml_client)
    try:
        pf_client._traces._get_cosmos_db_token(container_name=CosmosDBContainerName.SPAN)
    except FlowRequestException as e:
        ws_tracing_url = get_ws_tracing_base_url(workspace_triad)
        warning_msg = (
            f"Failed attempt to retrieve the Cosmos DB token: {str(e)}, "
            "this might because you have not initialized the Cosmos DB for the given workspace, "
            "or it's still be initializing.\n"
            f"Please open the following link to manually initialize it: {ws_tracing_url}."
        )
        _logger.warning(warning_msg)
