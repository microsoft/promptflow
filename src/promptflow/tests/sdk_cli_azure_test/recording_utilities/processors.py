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
    sanitize_upload_hash,
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


class AzureResourceProcessor(RecordingProcessor):
    """Sanitize sensitive data in Azure resource GET response."""

    def __init__(self):
        # datastore related
        self.storage_account_names = set()
        self.storage_container_names = set()

    def _sanitize_request_url_for_storage(self, uri: str) -> str:
        # this instance will store storage account names and container names
        # so we can apply the sanitization here with simple string replace rather than regex
        for account_name in self.storage_account_names:
            uri = uri.replace(account_name, SanitizedValues.FAKE_ACCOUNT_NAME)
        for container_name in self.storage_container_names:
            uri = uri.replace(container_name, SanitizedValues.FAKE_CONTAINER_NAME)
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
        for k in filter_keys:
            if k in body:
                body.pop(k)
        name = body["name"]
        body["name"] = SanitizedValues.WORKSPACE_NAME
        body["id"] = body["id"].replace(name, SanitizedValues.WORKSPACE_NAME)
        return body

    def _sanitize_response_for_arm_connection(self, body: Dict) -> Dict:
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
        self.storage_container_names.add(body["properties"]["containerName"])
        body["properties"]["accountName"] = SanitizedValues.FAKE_ACCOUNT_NAME
        body["properties"]["containerName"] = SanitizedValues.FAKE_CONTAINER_NAME
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
        if is_json_payload_request(request) and request.body is not None:
            body = request.body.decode("utf-8")
            body = sanitize_upload_hash(body)
            request.body = body.encode("utf-8")
        return request

    def process_response(self, response: Dict) -> Dict:
        if is_json_payload_response(response):
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
