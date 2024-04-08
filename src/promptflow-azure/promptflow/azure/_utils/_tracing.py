# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time
import typing

from azure.ai.ml import MLClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential, DefaultAzureCredential

from promptflow._constants import CosmosDBContainerName
from promptflow._sdk._utils import extract_workspace_triad_from_trace_provider
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.azure import PFClient
from promptflow.azure._restclient.flow_service_caller import FlowRequestException
from promptflow.exceptions import ErrorTarget, UserErrorException

_logger = get_cli_sdk_logger()

COSMOS_INIT_POLL_TIMEOUT_SECOND = 600  # 10 minutes
COSMOS_INIT_POLL_INTERVAL_SECOND = 30  # 30 seconds


def _get_credential() -> typing.Union[AzureCliCredential, DefaultAzureCredential]:
    try:
        credential = AzureCliCredential()
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception:  # pylint: disable=broad-except
        return DefaultAzureCredential()


def _create_trace_provider_value_user_error(message: str) -> UserErrorException:
    return UserErrorException(message=message, target=ErrorTarget.CONTROL_PLANE_SDK)


def _init_workspace_cosmos_db(init_cosmos_func: typing.Callable) -> None:
    # SDK will call PFS async API to execute workspace Cosmos DB initialization
    # and poll the status until it's done, the signal is the response is not None
    start_time = time.time()
    while True:
        try:
            cosmos_res = init_cosmos_func()
            if cosmos_res is not None:
                return
        except FlowRequestException:
            # ignore request error and continue to poll in next iteration
            pass
        # set a timeout here to prevent the potential infinite loop
        if int(time.time() - start_time) > COSMOS_INIT_POLL_TIMEOUT_SECOND:
            break
        prompt_msg = "The workspace Cosmos DB initialization is still in progress..."
        _logger.info(prompt_msg)
        time.sleep(COSMOS_INIT_POLL_INTERVAL_SECOND)
    # initialization does not finish in time, we need to ensure the Cosmos resource is ready
    # so print error log and raise error here
    error_msg = (
        "The workspace Cosmos DB initialization is still in progress "
        f"after {COSMOS_INIT_POLL_TIMEOUT_SECOND} seconds, "
        "please wait for a while and retry."
    )
    _logger.error(error_msg)
    raise Exception(error_msg)


def validate_trace_provider(value: str) -> None:
    """Validate `trace.provider` in pf config.

    1. the value is a valid ARM resource ID for Azure ML workspace
    2. the workspace exists
    3. the workspace Cosmos DB is initialized
    """
    # valid Azure ML workspace ARM resource ID; otherwise, a ValueError will be raised
    _logger.debug("Validating trace provider value...")
    try:
        workspace_triad = extract_workspace_triad_from_trace_provider(value)
    except ValueError as e:
        raise _create_trace_provider_value_user_error(str(e))

    # the workspace exists
    _logger.debug("Validating Azure ML workspace...")
    ml_client = MLClient(
        credential=_get_credential(),
        subscription_id=workspace_triad.subscription_id,
        resource_group_name=workspace_triad.resource_group_name,
        workspace_name=workspace_triad.workspace_name,
    )
    try:
        ml_client.workspaces.get(name=workspace_triad.workspace_name)
    except ResourceNotFoundError as e:
        raise _create_trace_provider_value_user_error(str(e))
    _logger.debug("Azure ML workspace is valid.")

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
        _init_workspace_cosmos_db(init_cosmos_func=pf_client._traces._init_cosmos_db)
    _logger.debug("The workspace Cosmos DB is initialized.")

    _logger.debug("Trace provider value is valid.")
