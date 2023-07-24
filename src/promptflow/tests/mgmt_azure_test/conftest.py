# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest
from azure.ai.ml import MLClient

from ._azure_utils import get_cred


@pytest.fixture
def ml_client(
    default_subscription_id: str,
    default_resource_group: str,
    default_workspace: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name=default_workspace,
        cloud="AzureCloud",
    )


@pytest.fixture
def ml_client_with_acr_access(
    default_subscription_id: str,
    default_resource_group: str,
    workspace_with_acr_access: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name=workspace_with_acr_access,
        cloud="AzureCloud",
    )


@pytest.fixture
def ml_client_int(
    default_subscription_id: str,
    default_resource_group: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id="d128f140-94e6-4175-87a7-954b9d27db16",
        resource_group_name=default_resource_group,
        workspace_name="promptflow-int",
        cloud="AzureCloud",
    )


@pytest.fixture
def ml_client_canary(
    default_subscription_id: str,
    default_resource_group: str,
) -> MLClient:
    """return a machine learning client using default e2e testing workspace"""

    return MLClient(
        credential=get_cred(),
        subscription_id=default_subscription_id,
        resource_group_name=default_resource_group,
        workspace_name="promptflow-canary-dev",
        cloud="AzureCloud",
    )
