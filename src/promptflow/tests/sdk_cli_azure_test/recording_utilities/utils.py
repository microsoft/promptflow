# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import re
from dataclasses import dataclass
from typing import Dict

from azure.core.credentials import AccessToken
from vcr.request import Request

from .constants import ENVIRON_TEST_MODE, SanitizedValues, TestMode


def get_test_mode_from_environ() -> str:
    return os.getenv(ENVIRON_TEST_MODE, TestMode.LIVE)


def is_live() -> bool:
    return get_test_mode_from_environ() == TestMode.LIVE


def is_record() -> bool:
    return get_test_mode_from_environ() == TestMode.RECORD


def is_replay() -> bool:
    return get_test_mode_from_environ() == TestMode.REPLAY


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
    account_name: str
    container_name: str
    endpoint: str


def mock_datastore_get_default(*args, **kwargs) -> MockDatastore:
    return MockDatastore(
        name="workspaceblobstore",
        account_name=SanitizedValues.FAKE_ACCOUNT_NAME,
        container_name=SanitizedValues.FAKE_CONTAINER_NAME,
        endpoint="core.windows.net",
    )


def mock_workspace_get(*args, **kwargs):
    from azure.ai.ml.entities import Workspace

    return Workspace(
        name=SanitizedValues.WORKSPACE_NAME,
        resource_group=SanitizedValues.RESOURCE_GROUP_NAME,
        discovery_url=SanitizedValues.DISCOVERY_URL,
        workspace_id=SanitizedValues.WORKSPACE_ID,
    )


def get_pf_client_for_replay():
    from azure.ai.ml import MLClient

    from promptflow.azure import PFClient

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


def sanitize_experiment_id(value: str) -> str:
    value = re.sub(
        r"(experimentId)=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"\1={}".format(SanitizedValues.WORKSPACE_ID),
        value,
        flags=re.IGNORECASE,
    )
    return value


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


def sanitize_username(value: str) -> str:
    value = re.sub(
        r"/(Users%2F)([^%?]+)(%2F|\?)",
        r"/\1{}\3".format(SanitizedValues.USERNAME),
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(Users/)([^/]+)(/)",
        r"\1{}\3".format(SanitizedValues.USERNAME),
        value,
        flags=re.IGNORECASE,
    )
    return value


def sanitize_flow_asset_id(value: str) -> str:
    # input: azureml://locations/<region>/workspaces/<workspace-id>/flows/<flow-id>
    # sanitize those with angle brackets
    sanitized_region = re.sub(
        r"/(locations)/[^/]+",
        r"/\1/{}".format(SanitizedValues.REGION),
        value,
        flags=re.IGNORECASE,
    )
    sanitized_workspace_id = re.sub(
        r"/(workspaces)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"/\1/{}".format(SanitizedValues.WORKSPACE_ID),
        sanitized_region,
        flags=re.IGNORECASE,
    )
    sanitized_flow_id = re.sub(
        r"/(flows)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"/\1/{}/".format(SanitizedValues.FLOW_ID),
        sanitized_workspace_id,
        flags=re.IGNORECASE,
    )
    return sanitized_flow_id


def sanitize_pfs_body(body: str) -> str:
    # sanitize workspace triad for longhand syntax asset, e.g. "batchDataInput.dataUri"
    body = sanitize_azure_workspace_triad(body)
    body_dict = json.loads(body)
    # /BulkRuns/submit
    if "runtimeName" in body_dict:
        body_dict["runtimeName"] = SanitizedValues.RUNTIME_NAME
    if "sessionId" in body_dict:
        body_dict["sessionId"] = SanitizedValues.SESSION_ID
    if "flowLineageId" in body:
        body_dict["flowLineageId"] = SanitizedValues.FLOW_LINEAGE_ID
    if "flowDefinitionResourceId" in body_dict:
        body_dict["flowDefinitionResourceId"] = sanitize_flow_asset_id(body_dict["flowDefinitionResourceId"])
    # PFS will help handle this field, so client does not need to pass this value
    if "runExperimentName" in body:
        body_dict["runExperimentName"] = ""
    return json.dumps(body_dict)


def sanitize_email(value: str) -> str:
    return re.sub(r"([\w\.-]+)@(microsoft.com)", r"{}@\2".format(SanitizedValues.EMAIL_USERNAME), value)


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
