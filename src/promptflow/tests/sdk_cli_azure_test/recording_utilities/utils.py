# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re
from dataclasses import dataclass

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Workspace
from azure.core.credentials import AccessToken

from promptflow.azure import PFClient

from .constants import SKIP_LIVE_RECORDING, TEST_RUN_LIVE, SanitizedValues


def is_live() -> bool:
    return os.getenv(TEST_RUN_LIVE, None) == "true"


def is_live_and_not_recording() -> bool:
    return is_live() and os.getenv(SKIP_LIVE_RECORDING, None) == "true"


class FakeTokenCredential:
    """Refer from Azure SDK for Python repository.

    https://github.com/Azure/azure-sdk-for-python/blob/main/tools/azure-sdk-tools/devtools_testutils/fake_credentials.py
    """

    def __init__(self):
        self.token = AccessToken("YOU SHALL NOT PASS", 0)
        self.get_token_count = 0

    def get_token(self, *args, **kwargs) -> AccessToken:
        self.get_token_count += 1
        return self.token


@dataclass
class MockDatastore:
    """Mock Datastore class for `DatastoreOperations.get_default().name`."""

    name: str


def mock_datastore_get_default(*args, **kwargs) -> MockDatastore:
    return MockDatastore(name="workspaceblobstore")


def mock_workspace_get(*args, **kwargs) -> Workspace:
    return Workspace(
        name=SanitizedValues.WORKSPACE_NAME,
        resource_group=SanitizedValues.RESOURCE_GROUP_NAME,
        discovery_url="https://eastus.api.azureml.ms/discovery",
    )


def get_pf_client_for_playback() -> PFClient:
    ml_client = MLClient(
        credential=FakeTokenCredential(),
        subscription_id=SanitizedValues.SUBSCRIPTION_ID,
        resource_group_name=SanitizedValues.RESOURCE_GROUP_NAME,
        workspace_name=SanitizedValues.WORKSPACE_NAME,
    )
    ml_client.datastores.get_default = mock_datastore_get_default
    ml_client.workspaces.get = mock_workspace_get
    return PFClient(ml_client=ml_client)


def sanitize_azure_workspace_triad(value: str) -> str:
    sanitized_sub = re.sub(
        "/(subscriptions)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"/\1/{}".format("00000000-0000-0000-0000-000000000000"),
        value,
        flags=re.IGNORECASE,
    )
    # for regex pattern for resource group name and workspace name, refer from:
    # https://learn.microsoft.com/en-us/rest/api/resources/resource-groups/create-or-update?tabs=HTTP
    sanitized_rg = re.sub(
        r"/(resourceGroups)/[-\w\._\(\)]+",
        r"/\1/{}".format("00000"),
        sanitized_sub,
        flags=re.IGNORECASE,
    )
    sanitized_ws = re.sub(
        r"/(workspaces)/[-\w\._\(\)]+[/?]",
        r"/\1/{}/".format("00000"),
        sanitized_rg,
        flags=re.IGNORECASE,
    )
    return sanitized_ws
