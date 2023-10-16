# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
from pathlib import Path
from typing import Dict, List

import vcr
from vcr.request import Request

from .constants import FILTER_HEADERS
from .processors import (
    AzureOpenAIConnectionProcessor,
    AzureResourceProcessor,
    AzureWorkspaceTriadProcessor,
    RecordingProcessor,
)
from .utils import is_live, is_live_and_not_recording


class PFAzureIntegrationTestRecording:
    def __init__(self, test_class, test_func_name: str):
        self.test_class = test_class
        self.test_func_name = test_func_name
        self.is_live = is_live()
        self.recording_file = self._get_recording_file()
        self.recording_processors = self._get_recording_processors()
        self.replay_processors = self._get_replay_processors()
        self.vcr = self._init_vcr()
        self._cm = None  # context manager from VCR
        self.cassette = None

    def _get_recording_file(self) -> Path:
        # recording files are expected to be located at "tests/test_configs/recordings"
        # test file path should locate at "tests/sdk_cli_azure_test/e2etests"
        test_file_path = Path(inspect.getfile(self.test_class)).resolve()
        recording_dir = (test_file_path.parent.parent.parent / "test_configs" / "recordings").resolve()
        recording_dir.mkdir(exist_ok=True)
        # recording filename pattern: {test_file_name}_{test_class_name}_{test_func_name}.yaml
        test_file_name = test_file_path.stem
        test_class_name = self.test_class.__name__
        recording_filename = f"{test_file_name}_{test_class_name}_{self.test_func_name}.yaml"
        recording_file = (recording_dir / recording_filename).resolve()
        if self.is_live and not is_live_and_not_recording() and recording_file.is_file():
            recording_file.unlink()
        return recording_file

    def _init_vcr(self) -> vcr.VCR:
        return vcr.VCR(
            cassette_library_dir=self.recording_file.parent.as_posix(),
            before_record_request=self._process_request_recording,
            before_record_response=self._process_response_recording,
            decode_compressed_response=True,
            record_mode="none" if not self.is_live else "all",
            filter_headers=FILTER_HEADERS,
        )

    def enter_vcr(self):
        self._cm = self.vcr.use_cassette(self.recording_file.as_posix())
        self.cassette = self._cm.__enter__()

    def exit_vcr(self):
        self._cm.__exit__()

    def _process_request_recording(self, request: Request) -> Request:
        if is_live_and_not_recording():
            return request

        if self.is_live:
            for processor in self.recording_processors:
                request = processor.process_request(request)
        else:
            for processor in self.replay_processors:
                request = processor.process_request(request)
        return request

    def _process_response_recording(self, response: Dict) -> Dict:
        if is_live_and_not_recording():
            return response

        response["body"]["string"] = response["body"]["string"].decode("utf-8")
        if self.is_live:
            # lower and filter some headers
            headers = {}
            for k in response["headers"]:
                if k.lower() not in FILTER_HEADERS:
                    headers[k.lower()] = response["headers"][k]
            response["headers"] = headers

            for processor in self.recording_processors:
                response = processor.process_response(response)
        else:
            for processor in self.replay_processors:
                response = processor.process_response(response)
        response["body"]["string"] = response["body"]["string"].encode("utf-8")
        return response

    def _get_recording_processors(self) -> List[RecordingProcessor]:
        return [
            AzureOpenAIConnectionProcessor(),
            AzureResourceProcessor(),
            AzureWorkspaceTriadProcessor(),
        ]

    def _get_replay_processors(self) -> List[RecordingProcessor]:
        return []
