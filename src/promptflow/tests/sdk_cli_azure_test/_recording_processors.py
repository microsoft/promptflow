# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import json

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
