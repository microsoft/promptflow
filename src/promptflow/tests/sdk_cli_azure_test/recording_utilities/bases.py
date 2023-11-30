# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import inspect
import json
from pathlib import Path
from typing import Dict, List

import vcr
from vcr import matchers
from vcr.request import Request

from .constants import FILTER_HEADERS, TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING, SanitizedValues
from .processors import (
    AzureMLExperimentIDProcessor,
    AzureOpenAIConnectionProcessor,
    AzureResourceProcessor,
    AzureWorkspaceTriadProcessor,
    DropProcessor,
    IndexServiceProcessor,
    PFSProcessor,
    RecordingProcessor,
    StorageProcessor,
    UserInfoProcessor,
)
from .utils import is_json_payload_request, is_live, is_record, is_replay, sanitize_pfs_body, sanitize_upload_hash
from .variable_recorder import VariableRecorder


class PFAzureIntegrationTestRecording:
    def __init__(self, test_class, test_func_name: str, user_object_id: str, tenant_id: str):
        self.test_class = test_class
        self.test_func_name = test_func_name
        self.user_object_id = user_object_id
        self.tenant_id = tenant_id
        self.recording_file = self._get_recording_file()
        self.recording_processors = self._get_recording_processors()
        self.vcr = self._init_vcr()
        self._cm = None  # context manager from VCR
        self.cassette = None
        self.variable_recorder = VariableRecorder()

    @staticmethod
    def from_test_case(test_class, test_func_name: str, **kwargs) -> "PFAzureIntegrationTestRecording":
        test_class_name = test_class.__name__
        user_object_id = kwargs.get("user_object_id", "")
        tenant_id = kwargs.get("tenant_id", "")
        if test_class_name in TEST_CLASSES_FOR_RUN_INTEGRATION_TEST_RECORDING:
            return PFAzureRunIntegrationTestRecording(
                test_class, test_func_name, user_object_id=user_object_id, tenant_id=tenant_id
            )
        else:
            return PFAzureIntegrationTestRecording(
                test_class, test_func_name, user_object_id=user_object_id, tenant_id=tenant_id
            )

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
        if is_record() and recording_file.is_file():
            recording_file.unlink()
        return recording_file

    def _init_vcr(self) -> vcr.VCR:
        _vcr = vcr.VCR(
            cassette_library_dir=self.recording_file.parent.as_posix(),
            before_record_request=self._process_request_recording,
            before_record_response=self._process_response_recording,
            decode_compressed_response=True,
            record_mode="none" if is_replay() else "all",
            filter_headers=FILTER_HEADERS,
        )
        _vcr.match_on += ("body",)
        return _vcr

    def enter_vcr(self):
        self._cm = self.vcr.use_cassette(self.recording_file.as_posix())
        self.cassette = self._cm.__enter__()

    def exit_vcr(self):
        if is_record():
            self._postprocess_recording()
        self._cm.__exit__()

    def _process_request_recording(self, request: Request) -> Request:
        if is_live():
            return request

        if is_record():
            for processor in self.recording_processors:
                request = processor.process_request(request)

        return request

    def _process_response_recording(self, response: Dict) -> Dict:
        if is_live():
            return response

        response["body"]["string"] = response["body"]["string"].decode("utf-8")
        if is_record():
            # lower and filter some headers
            headers = {}
            for k in response["headers"]:
                if k.lower() not in FILTER_HEADERS:
                    headers[k.lower()] = response["headers"][k]
            response["headers"] = headers

            for processor in self.recording_processors:
                response = processor.process_response(response)

        response["body"]["string"] = response["body"]["string"].encode("utf-8")
        return response

    def _get_recording_processors(self) -> List[RecordingProcessor]:
        return [
            AzureMLExperimentIDProcessor(),
            AzureOpenAIConnectionProcessor(),
            AzureResourceProcessor(),
            AzureWorkspaceTriadProcessor(),
            DropProcessor(),
            IndexServiceProcessor(),
            PFSProcessor(),
            StorageProcessor(),
            UserInfoProcessor(user_object_id=self.user_object_id, tenant_id=self.tenant_id),
        ]

    def get_or_record_variable(self, variable: str, default: str) -> str:
        if not is_replay():
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
    """Test class for run operations in Prompt Flow Azure.

    Different from other operations, run operations have:

    - duplicate network requests for stream run
    - blob storage requests contain upload hash
    - Submit and get run data API requests are indistinguishable without run name in body

    Use a separate class with more pre/post recording processing method or
    request matchers to handle above cases.
    """

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

    def _postprocess_recording(self) -> None:
        self._drop_duplicate_recordings()
        super(PFAzureRunIntegrationTestRecording, self)._postprocess_recording()

    def _drop_duplicate_recordings(self) -> None:
        # stream run operation contains two requests:
        # 1. get status; 2. get logs
        # before the run is terminated, there will be many duplicate requests
        # getting status/logs, which leads to infinite loop during replay
        # therefore apply such post process to drop those duplicate recordings
        dropped_recordings = []
        run_data_requests = dict()
        log_content_requests = dict()
        for req, resp in self.cassette.data:
            # run hisotry's rundata API
            if str(req.path).endswith("/rundata"):
                body = req.body.decode("utf-8")
                body_dict = json.loads(body)
                name = body_dict["runId"]
                run_data_requests[name] = (req, resp)
                continue
            if str(req.path).endswith("/logContent"):
                log_content_requests[req.uri] = (req, resp)
                continue
            dropped_recordings.append((req, resp))
        # append rundata recording(s)
        for req, resp in run_data_requests.values():
            dropped_recordings.append((req, resp))
        for req, resp in log_content_requests.values():
            dropped_recordings.append((req, resp))

        self.cassette.data = dropped_recordings
        return

    def _custom_request_path_matcher(self, r1: Request, r2: Request) -> bool:
        # for blob storage request, sanitize the upload hash in path
        if r1.host == r2.host and r1.host == SanitizedValues.BLOB_STORAGE_REQUEST_HOST:
            return sanitize_upload_hash(r1.path) == r2.path
        return r1.path == r2.path

    def _custom_request_body_matcher(self, r1: Request, r2: Request) -> bool:
        if is_json_payload_request(r1) and r1.body is not None:
            # note that `sanitize_upload_hash` is not idempotent
            # so we should not modify r1 directly
            # otherwise it will be sanitized multiple times with many zeros
            _r1 = copy.deepcopy(r1)
            body1 = _r1.body.decode("utf-8")
            body1 = sanitize_pfs_body(body1)
            body1 = sanitize_upload_hash(body1)
            _r1.body = body1.encode("utf-8")
            return matchers.body(_r1, r2)
        else:
            return matchers.body(r1, r2)
