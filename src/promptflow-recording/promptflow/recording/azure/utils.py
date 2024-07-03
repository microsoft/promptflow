# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import queue
import re
from dataclasses import dataclass
from typing import Any, Dict

import jwt
from azure.core.credentials import AccessToken
from vcr.request import Request

from .constants import ENVIRON_TEST_PACKAGE, SanitizedValues


PF_REQUEST_REPLACEMENTS = {
    "start_time": SanitizedValues.START_TIME,
    "timestamp": SanitizedValues.TIMESTAMP,
    "startTimeUtc": SanitizedValues.START_UTC,
    "endTimeUtc": SanitizedValues.END_UTC,
    "end_time": SanitizedValues.END_TIME,
    "runId": SanitizedValues.RUN_ID,
    "RunId": SanitizedValues.RUN_ID,
    # runDisplayName may be the same as RunID
    "runDisplayName": SanitizedValues.RUN_ID,
    "container": SanitizedValues.CONTAINER,
    "flowDefinitionBlobPath": SanitizedValues.FLOW_DEF,
    "flowArtifactsRootPath": SanitizedValues.ROOT_PF_PATH,
    "logFileRelativePath": SanitizedValues.EXEC_LOGS,
    "dataPath": SanitizedValues.DATA_PATH,
    "Outputs": SanitizedValues.OUTPUTS,
    "run_id": SanitizedValues.RUN_UUID,
    "run_uuid": SanitizedValues.RUN_UUID,
    "exp_id": SanitizedValues.EXP_UUID,
    "variantRunId": SanitizedValues.RUN_ID,
}


class FakeTokenCredential:
    """Refer from Azure SDK for Python repository.

    https://github.com/Azure/azure-sdk-for-python/blob/main/tools/azure-sdk-tools/devtools_testutils/fake_credentials.py
    """

    def __init__(self):
        token = jwt.encode(
            payload={
                "aud": "https://management.azure.com",
            },
            key="",
        )
        self.token = AccessToken(token, 0)
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
    credentials: FakeTokenCredential


def mock_datastore_get_default(*args, **kwargs) -> MockDatastore:
    return MockDatastore(
        name="workspaceblobstore",
        account_name=SanitizedValues.FAKE_ACCOUNT_NAME,
        container_name=SanitizedValues.FAKE_CONTAINER_NAME,
        endpoint="core.windows.net",
        credentials=FakeTokenCredential(),
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
        r"/(workspaces)/[-\w\._\(\)]+([/?][-\w\._\(\)]*)",
        r"/\1/{}\2".format("00000"),
        sanitized_rg,
        flags=re.IGNORECASE,
    )

    # workspace name can be the last part of the string
    # e.g. xxx/Microsoft.MachineLearningServices/workspaces/<workspace-name>
    # apply a special handle here to sanitize
    if sanitized_ws == sanitized_rg and sanitized_ws.startswith("https://"):
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
    value = sanitize_pf_run_ids(value)
    return value


def sanitize_pf_run_ids(value: str) -> str:
    """
    Replace Run ID on artifacts

    :param value: The value to be modified.
    :type value: str
    :returns: The modified string.
    """
    re_pf_exp_id = '.+?_\\w{6,8}'
    re_pf_run_id = '.+?_\\w{6,8}_\\d{8}_\\d{6}_\\d{6}'
    # Samnutize promptflow-like Run IDs.
    for left, right, eol in [
        ("ExperimentRun/dcid[.]", '', ''),
        ('promptflow/PromptFlowArtifacts/', '', ''),
        ('runs/', '/flow.flex.yaml', ''),
        ('runs/', '', '$'),
        ('runs/', '/.coverage.', ''),
        ('BulkRuns/', '', '$'),
            ('runs/', '/batchsync', '')]:
        value = re.sub(
            f"{left}{re_pf_run_id}{eol}{right}",
            f"{left.replace('[.]', '.')}{SanitizedValues.RUN_ID}{right}",
            value,
            flags=re.IGNORECASE,
        )
    # Sanitize the UUID-like Run IDs.
    re_uid = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    value = re.sub(
        f"experimentids/{re_uid}/runs/{re_uid}",
        f"experimentids/{SanitizedValues.EXP_UUID}/runs/{SanitizedValues.RUN_UUID}",
        value,
        flags=re.IGNORECASE,
    )
    # And the same for Promptflow experimentids
    value = re.sub(
        f"experimentids/{re_pf_exp_id}/runs/{re_pf_run_id}",
        f"experimentids/{SanitizedValues.EXP_UUID}/runs/{SanitizedValues.RUN_UUID}",
        value,
        flags=re.IGNORECASE,
    )
    # Sanitize the name of a coverage file
    value = re.sub(
        f"runs/{SanitizedValues.RUN_ID}/[.]coverage[^?]+",
        f"runs/{SanitizedValues.RUN_ID}/{SanitizedValues.COVERAGE}",
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


def sanitize_pfs_request_body(body: str) -> str:
    # sanitize workspace triad for longhand syntax asset, e.g. "batchDataInput.dataUri"
    body = sanitize_azure_workspace_triad(body)
    body_dict = json.loads(body)
    # /BulkRuns/submit
    if "runtimeName" in body_dict:
        body_dict["runtimeName"] = SanitizedValues.RUNTIME_NAME
    if "sessionId" in body_dict:
        body_dict["sessionId"] = SanitizedValues.SESSION_ID
    if "computeName" in body_dict:
        body_dict["computeName"] = SanitizedValues.COMPUTE_NAME
    if "flowLineageId" in body:
        body_dict["flowLineageId"] = SanitizedValues.FLOW_LINEAGE_ID
    if "flowDefinitionResourceId" in body_dict:
        body_dict["flowDefinitionResourceId"] = sanitize_flow_asset_id(body_dict["flowDefinitionResourceId"])
    # PFS will help handle this field, so client does not need to pass this value
    if "runExperimentName" in body:
        body_dict["runExperimentName"] = ""

    # promptflow-azure replay test does not require below sanitizations
    if os.getenv(ENVIRON_TEST_PACKAGE) == "promptflow-azure":
        return json.dumps(body_dict)

    # Go over the promptflow replacements
    for k, v in PF_REQUEST_REPLACEMENTS.items():
        if k in body_dict:
            body_dict[k] = v

    # Sanitize telemetry event
    if isinstance(body_dict, list) and "Microsoft.ApplicationInsights.Event" in body:
        body_dict = SanitizedValues.FAKE_APP_INSIGHTS

    return json.dumps(body_dict)


def sanitize_pfs_response_body(body: str) -> str:
    body_dict = json.loads(body)
    # BulkRuns/{flowRunId}
    if "studioPortalEndpoint" in body:
        body_dict["studioPortalEndpoint"] = sanitize_azure_workspace_triad(body_dict["studioPortalEndpoint"])
    if "studioPortalTraceEndpoint" in body:
        body_dict["studioPortalTraceEndpoint"] = sanitize_azure_workspace_triad(body_dict["studioPortalTraceEndpoint"])
    # TraceSessions
    if "accountEndpoint" in body:
        body_dict["accountEndpoint"] = ""
    if "resourceArmId" in body:
        body_dict["resourceArmId"] = ""
    # Remove token from the response.
    if "token" in body_dict and body_dict["token"]:
        body_dict["token"] = "sanitized_token_value"
    body_dict = sanitize_name(body_dict)
    # if "createdBy" in body_dict and "userName" in body_dict["createdBy"]:
    #     body_dict["createdBy"]["userName"] = "First Last"
    # if "lastModifiedBy" in body_dict and "userName" in body_dict["lastModifiedBy"]:
    #     body_dict["lastModifiedBy"]["userName"] = "First Last"
    if isinstance(body_dict, dict) and isinstance(
        body_dict.get("run"), dict) and isinstance(body_dict["run"].get("data"), dict) and isinstance(
            body_dict["run"]["data"].get("tags"), list):
        for dt_list in body_dict["run"]["data"]["tags"]:
            if isinstance(dt_list, dict) and dt_list.get("key") == "mlflow.user" and not dt_list.get(
                    "value", "").startswith("promptflow"):
                dt_list["value"] = "First Last"
    return json.dumps(body_dict)


def sanitize_name(dt_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize the developer first and last name.

    **Note:** The change happens inline. The dictionary is retured
    for convenience only.
    :param dt_data: The dictionary to be modified.
    :type dt_data: dict.
    :returns: The modified dictionary.
    """
    dict_que = queue.Queue()
    if isinstance(dt_data, dict):
        dict_que.put(dt_data)
    while not dict_que.empty():
        dt_curr = dict_que.get()
        for k in dt_curr.keys():
            if isinstance(dt_curr[k], dict):
                if k == "createdBy" or k == "lastModifiedBy" and "userName" in dt_curr[k]:
                    dt_curr[k]["userName"] = "First Last"
                else:
                    dict_que.put(dt_curr[k])
    return dt_data


def sanitize_email(value: str) -> str:
    return re.sub(r"([\w\.-]+)@(microsoft.com)", r"{}@\2".format(SanitizedValues.EMAIL_USERNAME), value)


def sanitize_file_share_flow_path(value: str) -> str:
    flow_folder_name = "simple_hello_world"
    if flow_folder_name not in value:
        return value
    start_index = value.index(flow_folder_name)
    flow_name_length = 38  # len("simple_hello_world-01-01-2024-00-00-00")
    flow_name = value[start_index: start_index + flow_name_length]
    return value.replace(flow_name, "flow_name")


def _sanitize_session_id_creating_automatic_runtime(value: str) -> str:
    value = re.sub(
        "/(FlowSessions)/[0-9a-f]{48}",
        r"/\1/{}".format(SanitizedValues.SESSION_ID),
        value,
        flags=re.IGNORECASE,
    )
    return value


def _sanitize_operation_id_polling_automatic_runtime(value: str) -> str:
    value = re.sub(
        "/(operations)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        r"/\1/{}".format(SanitizedValues.UUID),
        value,
        flags=re.IGNORECASE,
    )
    return value


def sanitize_automatic_runtime_request_path(value: str) -> str:
    return _sanitize_operation_id_polling_automatic_runtime(_sanitize_session_id_creating_automatic_runtime(value))


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


def is_httpx_response(response: Dict) -> bool:
    # different from other stubs in vcrpy, httpx response uses "content" instead of "body"
    # this leads to different handle logic to response
    # so we need a utility to check if a response is from httpx
    return "content" in response


def get_created_flow_name_from_flow_path(flow_path: str) -> str:
    # pytest fixture "created_flow" will create flow on file share with timestamp as suffix
    # we need to extract the flow name from the path
    # flow name is expected to start with "simple_hello_world" and follow with "/flow.dag.yaml"
    return flow_path[flow_path.index("simple_hello_world"): flow_path.index("/flow.dag.yaml")]
