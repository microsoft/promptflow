import json

import pytest

from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.utils._runtime_contract_util import normalize_dict_keys_camel_to_snake

from .._utils import get_config_file


@pytest.mark.unittest
def test_dict_normalize():
    d = {
        "FlowRunId": 1,
        "FlowId": 2,
        "SourceFlowRunId": 3,
        "SubmissionData": 4,
        "RunMode": 5,
        "Flow": 6,
        "createdBy": 7,
        "WorkspaceMsiTokenForStorageResource": 8,
        "abc": 1,
    }

    n_d = normalize_dict_keys_camel_to_snake(d)
    expected = {
        "flow_run_id": 1,
        "flow_id": 2,
        "source_flow_run_id": 3,
        "submission_data": 4,
        "run_mode": 5,
        "flow": 6,
        "created_by": 7,
        "workspace_msi_token_for_storage_resource": 8,
        "abc": 1,
    }
    assert n_d == expected


@pytest.mark.unittest
def test_deserialize_submit_flow_request():
    file_path = get_config_file("requests/submit_flow_request.json")
    with open(file_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    assert d is not None

    req = SubmitFlowRequest.deserialize(d)
    assert req is not None
    assert req.flow_id == "qa_with_bing"
    assert req.environment_variables["abc"] == "def"

    # Test desensitize
    data = SubmitFlowRequest.desensitize_to_json(req)
    data = json.loads(data)
    place_holder = "**data_scrubbed**"
    assert data["workspace_msi_token_for_storage_resource"] == place_holder
    assert data["submission_data"]["connections"] == place_holder
