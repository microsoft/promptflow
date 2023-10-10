# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import json
import re

from vcr.request import Request

from ._recording_utils import is_json_payload_request, is_json_payload_response


class RecordingProcessor:
    def process_request(self, request: Request) -> Request:  # pylint: disable=no-self-use
        return request

    def process_response(self, response: dict) -> dict:  # pylint: disable=no-self-use
        return response


class RequestUrlProcessor(RecordingProcessor):
    """Normalize request URL, '//' to '/'."""

    def process_request(self, request: Request) -> Request:
        request.uri = re.sub("(?<!:)//", "/", request.uri)
        return request


class DatastoreProcessor(RecordingProcessor):
    """Sanitize datastore sensitive data."""

    FAKE_KEY = "this is fake key"
    FAKE_ACCOUNT_NAME = "fake_account_name"
    FAKE_CONTAINER_NAME = "fake-container-name"

    def __init__(self):
        self.account_names = set()
        self.container_names = set()

    def _sanitize_head_request_uri(self, uri: str) -> str:
        if "blob.core.windows.net" in uri:
            # sanitize account name and container name
            for account_name in self.account_names:
                uri = uri.replace(account_name, self.FAKE_ACCOUNT_NAME)
            for container_name in self.container_names:
                uri = uri.replace(container_name, self.FAKE_CONTAINER_NAME)
        return uri

    def process_request(self, request: Request) -> Request:
        request.uri = self._sanitize_head_request_uri(request.uri)
        return request

    def _sanitize_get_response(self, body: dict) -> dict:
        if "id" in body and "datastores" in body["id"]:
            body["properties"]["subscriptionId"] = AzureWorkspaceTriadProcessor.SANITIZED_SUBSCRIPTION_ID
            body["properties"]["resourceGroup"] = AzureWorkspaceTriadProcessor.SANITIZED_RESOURCE_GROUP_NAME
            self.account_names.add(body["properties"]["accountName"])
            self.container_names.add(body["properties"]["containerName"])
            body["properties"]["accountName"] = self.FAKE_ACCOUNT_NAME
            body["properties"]["containerName"] = self.FAKE_CONTAINER_NAME
        return body

    def _sanitize_list_secrets_response(self, body: dict) -> dict:
        if "key" in body:
            b64_key = base64.b64encode(self.FAKE_KEY.encode("ascii"))
            body["key"] = str(b64_key, "ascii")
        return body

    def process_response(self, response: dict) -> dict:
        if is_json_payload_response(response):
            body = json.loads(response["body"]["string"])
            self._sanitize_get_response(body)
            self._sanitize_list_secrets_response(body)
            response["body"]["string"] = json.dumps(body)
        return response


class AzureWorkspaceTriadProcessor(RecordingProcessor):
    """Sanitize subscription id, resource group name and workspace name."""

    SANITIZED_SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000000"
    SANITIZED_RESOURCE_GROUP_NAME = "00000"
    SANITIZED_WORKSPACE_NAME = "00000"

    def _sanitize(self, val: str) -> str:
        sanitized_sub = re.sub(
            "/(subscriptions)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            r"/\1/{}".format(self.SANITIZED_SUBSCRIPTION_ID),
            val,
            flags=re.IGNORECASE,
        )
        # for regex pattern for resource group name and workspace name, refer from:
        # https://learn.microsoft.com/en-us/rest/api/resources/resource-groups/create-or-update?tabs=HTTP
        sanitized_rg = re.sub(
            r"/(resourceGroups)/[-\w\._\(\)]+",
            r"/\1/{}".format(self.SANITIZED_RESOURCE_GROUP_NAME),
            sanitized_sub,
            flags=re.IGNORECASE,
        )
        sanitized_ws = re.sub(
            r"/(workspaces)/[-\w\._\(\)]+",
            r"/\1/{}".format(self.SANITIZED_WORKSPACE_NAME),
            sanitized_rg,
            flags=re.IGNORECASE,
        )
        return sanitized_ws

    def process_request(self, request: Request) -> Request:
        request.uri = self._sanitize(request.uri)
        return request

    def process_response(self, response: dict) -> dict:
        response["body"]["string"] = self._sanitize(response["body"]["string"])
        return response


class UploadHashProcessor(RecordingProcessor):
    """Sanitize upload hash."""

    FAKE_UPLOAD_HASH = "000000000000000000000000000000000000"

    def _sanitize(self, val: str) -> str:
        val = re.sub(
            r"(az-ml-artifacts)/([0-9a-f]{32})",
            r"\1/{}".format(self.FAKE_UPLOAD_HASH),
            val,
            flags=re.IGNORECASE,
        )
        val = re.sub(
            r"(LocalUpload)/([0-9a-f]{32})",
            r"\1/{}".format(self.FAKE_UPLOAD_HASH),
            val,
            flags=re.IGNORECASE,
        )
        return val

    def _sanitize_request_body(self, body: bytes) -> bytes:
        body = body.decode("utf-8")
        body = self._sanitize(body)
        body = body.encode("utf-8")
        return body

    def process_request(self, request: Request) -> Request:
        request.uri = self._sanitize(request.uri)
        if is_json_payload_request(request):
            request.body = self._sanitize_request_body(request.body)
        return request

    def process_response(self, response: dict) -> dict:
        response["body"]["string"] = self._sanitize(response["body"]["string"])
        return response
