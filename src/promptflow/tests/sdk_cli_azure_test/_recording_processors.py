# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import json
import re

from vcr.request import Request

from ._recording_utils import is_json_payload_response


class RecordingProcessor:
    def process_request(self, request: Request) -> Request:  # pylint: disable=no-self-use
        return request

    def process_response(self, response: dict) -> dict:  # pylint: disable=no-self-use
        return response


class DatastoreKeyProcessor(RecordingProcessor):
    """Sanitize datastore key in listSecrets response."""

    FAKE_KEY = "this is fake key"

    def process_response(self, response: dict) -> dict:
        if is_json_payload_response(response):
            body = json.loads(response["body"]["string"])
            if "key" in body:
                b64_key = base64.b64encode(self.FAKE_KEY.encode("ascii"))
                body["key"] = str(b64_key, "ascii")
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
