import json
import sys
import uuid
from pathlib import Path

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow_test.run_test_utils import FlowRequestService, assert_result_valid
from promptflow_test.utils import (
    _save_result_in_temp_folder,
    ensure_request_file,
    load_and_convert_to_raw,
    load_request_to_raw,
)

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/e2e_samples"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))

BUILTIN_SAMPLE_FLOW_RUNS = ["qa_with_bing.json", "classification_accuracy_eval.json"]

BUILTIN_SAMPLE_BULK_TESTS = [
    ("qa_with_bing.json"),
    ("qa_with_bing_variants.json"),
    ("classification_variants_with_eval.json"),
    ("classification_with_eval.json"),
]


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
class TestSamples:
    def assert_success(self, result, result_file):
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert isinstance(result["flow_runs"], list)
        for run in result["flow_runs"]:
            msg = f"Flow run {run['run_id']} failed, see {result_file} for more details."
            assert isinstance(run, dict)
            assert run["status"] == "Completed", msg

    @pytest.mark.parametrize(
        "file_name",
        BUILTIN_SAMPLE_FLOW_RUNS,
    )
    def test_executor_flow_run(self, basic_executor, file_name) -> None:
        """Test the basic flow that has three flow runs."""
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_request_to_raw(json_file, run_mode=RunMode.Flow)
        request_data = SubmitFlowRequest.deserialize(request_data)
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        result_file = _save_result_in_temp_folder(result, file_name)
        self.assert_success(result, result_file)

    @pytest.mark.parametrize(
        "file_name",
        BUILTIN_SAMPLE_BULK_TESTS,
    )
    @pytest.mark.usefixtures("set_azureml_config")
    def test_executor_bulktest(self, ml_client, basic_executor, file_name) -> None:
        """Test the basic flow that has three flow runs."""
        json_file = Path(JSON_DATA_ROOT) / file_name
        json_file = ensure_request_file(json_file)
        with open(json_file, "r") as f:
            request = json.load(f)
        request_data = load_and_convert_to_raw(json_file, run_mode=RunMode.BulkTest)
        request_data.submission_data.bulk_test_id = str(uuid.uuid4())
        request_data.submission_data.baseline_variant_id = "variant_0"
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        assert_result_valid(
            request=request,
            response=result,
            request_service=FlowRequestService.RUNTIME,
            mode=RunMode.BulkTest,
            ml_client=ml_client,
        )
