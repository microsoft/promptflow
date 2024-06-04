# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import json
from typing import Dict

from vcr.request import Request

from .constants import AzureMLResourceTypes, SanitizedValues
from .utils import (
    is_json_payload_request,
    is_json_payload_response,
    sanitize_azure_workspace_triad,
    sanitize_email,
    sanitize_experiment_id,
    sanitize_pfs_request_body,
    sanitize_pfs_response_body,
    sanitize_upload_hash,
    sanitize_username,
)


class RecordingProcessor:
    def process_request(self, request: Request) -> Request:
        return request

    def process_response(self, response: Dict) -> Dict:
        return response


class AzureWorkspaceTriadProcessor(RecordingProcessor):
    """Sanitize subscription id, resource group name and workspace name."""

    def process_request(self, request: Request) -> Request:
        request.uri = sanitize_azure_workspace_triad(request.uri)
        return request

    def process_response(self, response: Dict) -> Dict:
        response["body"]["string"] = sanitize_azure_workspace_triad(response["body"]["string"])
        return response


class AzureMLExperimentIDProcessor(RecordingProcessor):
    """Sanitize Azure ML experiment id, currently we use workspace id as the value."""

    def process_request(self, request: Request) -> Request:
        request.uri = sanitize_experiment_id(request.uri)
        return request

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            if "experimentId" in response["body"]["string"]:
                body = json.loads(response["body"]["string"])
                if "experimentId" in body:
                    body["experimentId"] = SanitizedValues.WORKSPACE_ID
                response["body"]["string"] = json.dumps(body)
        return response


class AzureResourceProcessor(RecordingProcessor):
    """Sanitize sensitive data in Azure resource GET response."""

    def __init__(self):
        # datastore related
        self.storage_account_names = set()
        self.storage_container_names = set()
        self.file_share_names = set()

    def _sanitize_request_url_for_storage(self, uri: str) -> str:
        # this instance will store storage account names and container names
        # so we can apply the sanitization here with simple string replace rather than regex
        for account_name in self.storage_account_names:
            uri = uri.replace(account_name, SanitizedValues.FAKE_ACCOUNT_NAME)
        for container_name in self.storage_container_names:
            # container name in uri should have special pattern
            uri = uri.replace(
                f"blob.core.windows.net/{container_name}/",
                f"blob.core.windows.net/{SanitizedValues.FAKE_CONTAINER_NAME}/",
            )
        for file_share_name in self.file_share_names:
            uri = uri.replace(file_share_name, SanitizedValues.FAKE_FILE_SHARE_NAME)
        return uri

    def process_request(self, request: Request) -> Request:
        request.uri = self._sanitize_request_url_for_storage(request.uri)
        return request

    def _sanitize_response_body(self, body: Dict) -> Dict:
        resource_type = body.get("type")
        if resource_type == AzureMLResourceTypes.WORKSPACE:
            body = self._sanitize_response_for_workspace(body)
        elif resource_type == AzureMLResourceTypes.CONNECTION:
            body = self._sanitize_response_for_arm_connection(body)
        elif resource_type == AzureMLResourceTypes.DATASTORE:
            body = self._sanitize_response_for_datastore(body)
        return body

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            body = json.loads(response["body"]["string"])
            if isinstance(body, dict):
                # response can be a list sometimes (e.g. get workspace datastores)
                # need to sanitize each with a for loop
                if "value" in body:
                    resources = body["value"]
                    for i in range(len(resources)):
                        resources[i] = self._sanitize_response_body(resources[i])
                    body["value"] = resources
                else:
                    body = self._sanitize_response_body(body)
            response["body"]["string"] = json.dumps(body)
        return response

    def _sanitize_response_for_workspace(self, body: Dict) -> Dict:
        filter_keys = ["identity", "properties", "systemData"]
        discovery_url = body.get("properties", {}).get("discoveryUrl", SanitizedValues.DISCOVERY_URL)
        for k in filter_keys:
            if k in body:
                body.pop(k)
        # need during the constructor of FlowServiceCaller (for vNet case)
        body["properties"] = {"discoveryUrl": discovery_url}
        name = body["name"]
        body["name"] = SanitizedValues.WORKSPACE_NAME
        body["id"] = body["id"].replace(name, SanitizedValues.WORKSPACE_NAME)
        return body

    def _sanitize_response_for_arm_connection(self, body: Dict) -> Dict:
        # Note: list api returns credentials as null
        if body["properties"]["credentials"] is not None:
            if body["properties"]["authType"] == "CustomKeys":
                # custom connection, sanitize "properties.credentials.keys"
                body["properties"]["credentials"]["keys"] = {}
            else:
                # others, sanitize "properties.credentials.key"
                body["properties"]["credentials"]["key"] = "_"
        body["properties"]["target"] = "_"
        return body

    def _sanitize_response_for_datastore(self, body: Dict) -> Dict:
        body["properties"]["subscriptionId"] = SanitizedValues.SUBSCRIPTION_ID
        body["properties"]["resourceGroup"] = SanitizedValues.RESOURCE_GROUP_NAME
        self.storage_account_names.add(body["properties"]["accountName"])
        body["properties"]["accountName"] = SanitizedValues.FAKE_ACCOUNT_NAME
        # blob storage
        if "containerName" in body["properties"]:
            self.storage_container_names.add(body["properties"]["containerName"])
            body["properties"]["containerName"] = SanitizedValues.FAKE_CONTAINER_NAME
        # file share
        elif "fileShareName" in body["properties"]:
            self.file_share_names.add(body["properties"]["fileShareName"])
            body["properties"]["fileShareName"] = SanitizedValues.FAKE_FILE_SHARE_NAME

        return body


class AzureOpenAIConnectionProcessor(RecordingProcessor):
    """Sanitize api_base in AOAI connection GET response."""

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            body = json.loads(response["body"]["string"])
            if isinstance(body, dict) and body.get("connectionType") == "AzureOpenAI":
                body["configs"]["api_base"] = SanitizedValues.FAKE_API_BASE
            response["body"]["string"] = json.dumps(body)
        return response


class StorageProcessor(RecordingProcessor):
    """Sanitize sensitive data during storage operations when submit run."""

    def process_request(self, request: Request) -> Request:
        request.uri = sanitize_upload_hash(request.uri)
        request.uri = sanitize_username(request.uri)
        if is_json_payload_request(request) and request.body is not None:
            body = request.body.decode("utf-8")
            body = sanitize_upload_hash(body)
            body = sanitize_username(body)
            request.body = body.encode("utf-8")
        return request

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            response["body"]["string"] = sanitize_username(response["body"]["string"])
            body = json.loads(response["body"]["string"])
            if isinstance(body, dict):
                self._sanitize_list_secrets_response(body)
            response["body"]["string"] = json.dumps(body)
        return response

    def _sanitize_list_secrets_response(self, body: Dict) -> Dict:
        if "key" in body:
            b64_key = base64.b64encode(SanitizedValues.FAKE_KEY.encode("ascii"))
            body["key"] = str(b64_key, "ascii")
        return body


class DropProcessor(RecordingProcessor):
    """Ignore some requests that won't be used during playback."""

    def process_request(self, request: Request) -> Request:
        if "/metadata/identity/oauth2/token" in request.path:
            return None
        return request


class PFSProcessor(RecordingProcessor):
    """Sanitize request/response for PFS operations."""

    def process_request(self, request: Request) -> Request:
        if is_json_payload_request(request) and request.body is not None:
            body = request.body.decode("utf-8")
            body = sanitize_pfs_request_body(body)
            request.body = body.encode("utf-8")
        return request

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            response["body"]["string"] = sanitize_pfs_response_body(response["body"]["string"])
        return response


class UserInfoProcessor(RecordingProcessor):
    """Sanitize user object id and tenant id in responses."""

    def __init__(self, user_object_id: str, tenant_id: str):
        self.user_object_id = user_object_id
        self.tenant_id = tenant_id

    def process_request(self, request: Request) -> Request:
        if is_json_payload_request(request) and request.body is not None:
            body = request.body.decode("utf-8")
            body = str(body).replace(self.user_object_id, SanitizedValues.USER_OBJECT_ID)
            body = body.replace(self.tenant_id, SanitizedValues.TENANT_ID)
            request.body = body.encode("utf-8")
        return request

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            response["body"]["string"] = str(response["body"]["string"]).replace(
                self.user_object_id, SanitizedValues.USER_OBJECT_ID
            )
            response["body"]["string"] = str(response["body"]["string"]).replace(
                self.tenant_id, SanitizedValues.TENANT_ID
            )
        return response


class IndexServiceProcessor(RecordingProcessor):
    """Sanitize index service responses."""

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
            if "continuationToken" in response["body"]["string"]:
                body = json.loads(response["body"]["string"])
                body.pop("continuationToken", None)
                response["body"]["string"] = json.dumps(body)
        return response


class EmailProcessor(RecordingProcessor):
    """Sanitize email address in responses."""

    def process_response(self, response: Dict) -> Dict:
        response["body"]["string"] = sanitize_email(response["body"]["string"])
        return response
