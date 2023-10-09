# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from vcr.request import Request


class RecordingProcessor:
    def process_request(self, request: Request) -> Request:  # pylint: disable=no-self-use
        return request

    def process_response(self, response: dict) -> dict:  # pylint: disable=no-self-use
        return response
