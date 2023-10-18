# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
import json
from pathlib import Path
from typing import Dict, List

import vcr
from vcr.request import Request

from .constants import FILTER_HEADERS, TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING, SanitizedValues
from .processors import (
    AzureOpenAIConnectionProcessor,
    AzureResourceProcessor,
    AzureWorkspaceTriadProcessor,
    DropProcessor,
    RecordingProcessor,
    StorageProcessor,
    TenantProcessor,
)
from .utils import is_live, is_live_and_not_recording, sanitize_upload_hash
from .variable_recorder import VariableRecorder


class PFAzureIntegrationTestRecording:
    def __init__(self, test_class, test_func_name: str, tenant_id: str):
        self.test_class = test_class
        self.test_func_name = test_func_name
        self.tenant_id = tenant_id
        self.is_live = is_live()
        self.recording_file = self._get_recording_file()
        self.recording_processors = self._get_recording_processors()
        self.replay_processors = self._get_replay_processors()
        self.vcr = self._init_vcr()
        self._cm = None  # context manager from VCR
        self.cassette = None
        self.variable_recorder = VariableRecorder()

    @staticmethod
    def from_test_case(test_class, test_func_name: str, **kwargs) -> "PFAzureIntegrationTestRecording":
        test_class_name = test_class.__name__
        tenant_id = kwargs.get("tenant_id", "")
        if test_class_name in TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING:
            return PFAzureRunIntegrationTestRecording(test_class, test_func_name, tenant_id=tenant_id)
        else:
            return PFAzureIntegrationTestRecording(test_class, test_func_name, tenant_id=tenant_id)

    def _get_recording_file(self) -> Path:
        # recording files are expected to be located at "tests/test_configs/recordings"
        # test file path should locate at "tests/sdk_cli_azure_test/e2etests"
        test_file_path = Path(inspect.getfile(self.test_class)).resolve()
        recording_dir = (test_file_path.parent.parent.parent / "test_configs" / "recordings").resolve()
        recording_dir.mkdir(exist_ok=True)

        test_file_name = test_file_path.stem
        test_class_name = self.test_class.__name__
        if "[" in self.test_func_name:
            # for tests that use pytest.mark.parametrize, there will be "[]" in test function name
            # recording filename pattern:
            # {test_file_name}_{test_class_name}_{test_func_name}/{parameter_id}.yaml
            test_func_name, parameter_id = self.test_func_name.split("[")
            parameter_id = parameter_id.rstrip("]")
            test_func_dir = (recording_dir / f"{test_file_name}_{test_class_name}_{test_func_name}").resolve()
            test_func_dir.mkdir(exist_ok=True)
            recording_file = (test_func_dir / f"{parameter_id}.yaml").resolve()
        else:
            # for most remaining tests
            # recording filename pattern: {test_file_name}_{test_class_name}_{test_func_name}.yaml
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
        if self.is_live and not is_live_and_not_recording():
            self._postprocess_recording()
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
            DropProcessor(),
            TenantProcessor(tenant_id=self.tenant_id),
        ]

    def _get_replay_processors(self) -> List[RecordingProcessor]:
        return []

    def get_or_record_variable(self, variable: str, default: str) -> str:
        if is_live():
            return self.variable_recorder.get_or_record_variable(variable, default)
        else:
            # return variable when playback, which is expected to be sanitized
            return variable

    def _postprocess_recording(self) -> None:
        self._apply_replacement_for_recordings()
        return

    def _apply_replacement_for_recordings(self) -> None:
        for i in range(len(self.cassette.data)):
            req, resp = self.cassette.data[i]
            req = self.variable_recorder.sanitize_request(req)
            resp = self.variable_recorder.sanitize_response(resp)
            self.cassette.data[i] = (req, resp)
        return


class PFAzureRunIntegrationTestRecording(PFAzureIntegrationTestRecording):
    def _init_vcr(self) -> vcr.VCR:
        _vcr = super(PFAzureRunIntegrationTestRecording, self)._init_vcr()
        _vcr.register_matcher("path", self._custom_request_path_matcher)
        _vcr.register_matcher("body", self._custom_request_body_matcher)
        return _vcr

    def enter_vcr(self):
        self._cm = self.vcr.use_cassette(
            self.recording_file.as_posix(),
            allow_playback_repeats=True,
            filter_query_parameters=["api-version"],
        )
        self.cassette = self._cm.__enter__()

    def _get_recording_processors(self) -> List[RecordingProcessor]:
        recording_processors = super(PFAzureRunIntegrationTestRecording, self)._get_recording_processors()
        recording_processors.append(StorageProcessor())
        return recording_processors

    def _postprocess_recording(self) -> None:
        self._drop_duplicate_recordings()
        super(PFAzureRunIntegrationTestRecording, self)._postprocess_recording()

    def _drop_duplicate_recordings(self) -> None:
        dropped_recordings = []
        run_data_requests = dict()
        for req, resp in self.cassette.data:
            # run hisotry's rundata API
            if str(req.path).endswith("rundata"):
                body = req.body.decode("utf-8")
                body_dict = json.loads(body)
                name = body_dict["runId"]
                run_data_requests[name] = (req, resp)
                continue
            dropped_recordings.append((req, resp))
        # append rundata recording(s)
        for req, resp in run_data_requests.values():
            dropped_recordings.append((req, resp))

        self.cassette.data = dropped_recordings
        return

    def _custom_request_path_matcher(self, r1: Request, r2: Request) -> bool:
        # for blob storage request, sanitize the upload hash in path
        if r1.host == r2.host and r1.host == SanitizedValues.BLOB_STORAGE_REQUEST_HOST:
            return sanitize_upload_hash(r1.path) == r2.path
        return r1.path == r2.path

    def _custom_request_body_matcher(self, r1: Request, r2: Request) -> bool:
        if r1.path == r2.path:
            # /BulkRuns/submit - submit run, match by "runId" in body
            # /rundata - get run, match by "runId" in body
            if r1.path.endswith("/BulkRuns/submit") or r1.path.endswith("/rundata"):
                return r1.body.get("runId") == r2.body.get("runId")
            else:
                # we don't match by body for other requests, so return True
                return True
        else:
            # path no match, so this pair shall not match
            return False
