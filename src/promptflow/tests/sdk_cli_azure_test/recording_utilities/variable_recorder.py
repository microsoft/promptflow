# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Dict

from vcr.request import Request

from .utils import is_json_payload_request


class VariableRecorder:
    def __init__(self):
        self.variables = dict()

    def get_or_record_variable(self, variable: str, default: str) -> str:
        return self.variables.setdefault(variable, default)

    def sanitize_request(self, request: Request) -> Request:
        request.uri = self._sanitize(request.uri)
        if is_json_payload_request(request) and request.body is not None:
            body = request.body.decode("utf-8")
            body = self._sanitize(body)
            request.body = body.encode("utf-8")
        return request

    def sanitize_response(self, response: Dict) -> Dict:
        response["body"]["string"] = response["body"]["string"].decode("utf-8")
        response["body"]["string"] = self._sanitize(response["body"]["string"])
        response["body"]["string"] = response["body"]["string"].encode("utf-8")
        return response

    def _sanitize(self, value: str) -> str:
        for k, v in self.variables.items():
            value = value.replace(v, k)
        return value
