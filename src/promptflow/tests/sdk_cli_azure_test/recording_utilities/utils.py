# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import re
from dataclasses import dataclass
from typing import Dict

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Workspace
from azure.core.credentials import AccessToken
from vcr.request import Request

from promptflow.azure import PFClient

from .constants import SKIP_LIVE_RECORDING, TEST_RUN_LIVE, SanitizedValues


def is_live() -> bool:
    return os.getenv(TEST_RUN_LIVE, "true") == "true"


def is_live_and_not_recording() -> bool:
    return is_live() and os.getenv(SKIP_LIVE_RECORDING, "true") == "true"


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
        discovery_url=SanitizedValues.DISCOVERY_URL,
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

    # workspace name can be the last part of the string
    # e.g. xxx/Microsoft.MachineLearningServices/workspaces/<workspace-name>
    # apply a special handle here to sanitize
    if sanitized_ws.startswith("https://"):
        split1, split2 = sanitized_ws.split("/")[-2:]
        if split1 == "workspaces":
            sanitized_ws = sanitized_ws.replace(split2, SanitizedValues.WORKSPACE_NAME)

    return sanitized_ws


def sanitize_upload_hash(value: str) -> str:
    value = re.sub(
        r"(az-ml-artifacts)/([0-9a-f]{32})",
        r"\1/{}".format(SanitizedValues.UPLOAD_HASH),
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(LocalUpload)/([0-9a-f]{32})",
        r"\1/{}".format(SanitizedValues.UPLOAD_HASH),
        value,
        flags=re.IGNORECASE,
    )
    return value


def _is_json_payload(headers: Dict, key: str) -> bool:
    if not headers:
        return False
    content_type = headers.get(key)
    if not content_type:
        return False
    # content-type can be an array, e.g. ["application/json; charset=utf-8"]
    content_type = content_type[0] if isinstance(content_type, list) else content_type
    content_type = content_type.split(";")[0].lower()
    return "application/json" in content_type


def is_json_payload_request(request: Request) -> bool:
    headers = request.headers
    return _is_json_payload(headers, key="Content-Type")


def is_json_payload_response(response: Dict) -> bool:
    headers = response.get("headers")
    # PFAzureIntegrationTestRecording will lower keys in response headers
    return _is_json_payload(headers, key="content-type")
