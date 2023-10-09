# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import os
import unittest
from pathlib import Path
from typing import List, Type
from urllib.parse import parse_qs, urlparse

import vcr
from vcr.request import Request

from ._recording_processors import AzureWorkspaceTriadProcessor, DatastoreKeyProcessor, RecordingProcessor

TEST_RUN_LIVE = "PROMPT_FLOW_TEST_RUN_LIVE"
SKIP_LIVE_RECORDING = "PROMPT_FLOW_SKIP_LIVE_RECORDING"


def is_live() -> bool:
    return os.environ.get(TEST_RUN_LIVE, None) == "true"


def is_live_and_not_recording() -> bool:
    return is_live() and os.environ.get(SKIP_LIVE_RECORDING, None) == "true"


class PFAzureIntegrationTestCase(unittest.TestCase):
    FILTER_HEADERS = [
        "authorization",
        "client-request-id",
        "retry-after",
        "x-ms-client-request-id",
        "x-ms-correlation-request-id",
        "x-ms-ratelimit-remaining-subscription-reads",
        "x-ms-request-id",
        "x-ms-routing-request-id",
        "x-ms-gateway-service-instanceid",
        "x-ms-ratelimit-remaining-tenant-reads",
        "x-ms-served-by",
        "x-ms-authorization-auxiliary",
        "x-ms-correlation-request-id",
        "x-ms-ratelimit-remaining-subscription-writes",
        "x-ms-request-id",
        "x-ms-response-type",
        "x-ms-routing-request-id",
        "x-request-time",
        "x-aml-cluster",
        "aml-user-token",
        "request-context",
    ]

    def __init__(self, method_name: str) -> None:
        super(PFAzureIntegrationTestCase, self).__init__(method_name)

        self.recording_processors = self._get_recording_processors()
        self.playback_processors = self._get_playback_processors()

        test_file_path = Path(inspect.getfile(self.__class__)).resolve()
        recording_dir = (test_file_path.parent / "recordings").resolve()

        self.is_live = is_live()

        self.vcr = vcr.VCR(
            cassette_library_dir=recording_dir.as_posix(),
            before_record_request=self._process_request_recording,
            before_record_response=self._process_response_recording,
            decode_compressed_response=True,
            record_mode="none" if not self.is_live else "all",
            filter_headers=self.FILTER_HEADERS,
        )
        self.vcr.register_matcher("query", self._custom_request_query_matcher)

        test_file_name = test_file_path.stem
        test_class_name = self.__class__.__name__
        recording_filename = f"{test_file_name}_{test_class_name}_{method_name}.yaml"
        self.recording_file = (recording_dir / recording_filename).resolve()

        if self.is_live and not is_live_and_not_recording() and self.recording_file.is_file():
            self.recording_file.unlink()

    def setUp(self) -> None:
        super(PFAzureIntegrationTestCase, self).setUp()

        # set up cassette
        cm = self.vcr.use_cassette(self.recording_file.as_posix())
        self.cassette = cm.__enter__()
        self.addCleanup(cm.__exit__)

    def _process_request_recording(self, request: Request) -> Request:
        if is_live_and_not_recording():
            return request

        if self.is_live:
            for processor in self.recording_processors:
                request = processor.process_request(request)
                if not request:
                    break
        else:
            for processor in self.playback_processors:
                request = processor.process_request(request)
                if not request:
                    break

        return request

    def _process_response_recording(self, response: dict) -> dict:
        if is_live_and_not_recording():
            return response

        response["body"]["string"] = bytes(response["body"]["string"]).decode("utf-8")

        if self.is_live:
            # lower and filter some headers
            headers = {}
            for k in response["headers"]:
                if k.lower() not in self.FILTER_HEADERS:
                    headers[k.lower()] = response["headers"][k]
            response["headers"] = headers

            for processor in self.recording_processors:
                response = processor.process_response(response)
                if not response:
                    break
        else:
            for processor in self.playback_processors:
                response = processor.process_response(response)
                if not response:
                    break

        response["body"]["string"] = str(response["body"]["string"]).encode("utf-8")

        return response

    def _get_recording_processors(self) -> List[Type[RecordingProcessor]]:
        return [
            AzureWorkspaceTriadProcessor(),
            DatastoreKeyProcessor(),
        ]

    def _get_playback_processors(self) -> List[Type[RecordingProcessor]]:
        return [
            AzureWorkspaceTriadProcessor(),
        ]

    def _custom_request_query_matcher(self, r1: Request, r2: Request) -> bool:
        # VCR.py will guarantee method, scheme, host and port match
        # in prompt flow scenario, we also want to ensure query parameters match
        url1 = urlparse(r1.uri)
        url2 = urlparse(r2.uri)
        q1 = parse_qs(url1.query)
        q2 = parse_qs(url2.query)
        shared_keys = set(q1.keys()).intersection(set(q2.keys()))

        if len(shared_keys) != len(q1) or len(shared_keys) != len(q2):
            return False
        for k in shared_keys:
            if q1[k][0].lower() != q2[k][0].lower():
                return False

        return True
