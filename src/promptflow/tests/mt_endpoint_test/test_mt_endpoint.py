import json
import logging
from pathlib import Path

import mlflow
import pytest
from utils.run_history_client import RunHistoryClient

from promptflow._constants import AzureStorageType
from promptflow_test.utils import load_json

from .mt_client import PromptflowClient

TEST_ROOT = Path(__file__).parent.parent / "test_configs"

E2E_SAMPLES_PATH = TEST_ROOT / "e2e_samples"
E2E_FLOW_SAMPLES_PATH = E2E_SAMPLES_PATH / "flow_submission"
E2E_DIRECTORY_SAMPLES_PATH = E2E_SAMPLES_PATH / "directory_based_submission"

TOOL_META_RESPONSE_PATH = TEST_ROOT / "meta_responses"

BULK_TESTS_LIST = ["classification_variants_with_eval.json", "classification_with_eval.json"]

BULK_TESTS_FROM_FILESHARE_LIST = ["classification_accuracy_eval"]

E2E_FLOW_JSON_TEST_CASES = [
    "flow_run.json",
    "flow_run_variant.json",
    "bulk_run.json",
    "bulk_run_variant.json",
    "bulk_run_eval.json",
    "bulk_run_variant_eval.json",
    "single_node_run.json",
    "single_node_variant_run.json",
]

E2E_FLOW_YAML_TEST_CASES = [
    ("flow_run.json", False),
    ("bulk_run.json", True),
]

TOOL_META_TEST_CASES = ["python_tool_meta.json", "llm_tool_meta.json", "prompt_tool_meta.json"]


@pytest.mark.mt_endpointtest
class TestMTEndpoint:
    @pytest.mark.parametrize(
        "case_file_name",
        E2E_FLOW_JSON_TEST_CASES,
    )
    def test_flow_e2e_use_json(self, promptflow_client: PromptflowClient, case_file_name):
        test_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / case_file_name
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_json(test_flow_file)
        logging.info(mt_response)
        assert mt_response.is_run_completed

    @pytest.mark.parametrize(
        "case_file_name, is_bulk_run",
        E2E_FLOW_YAML_TEST_CASES,
    )
    def test_flow_e2e_use_yaml(self, promptflow_client: PromptflowClient, case_file_name, is_bulk_run):
        test_flow_file = Path(E2E_DIRECTORY_SAMPLES_PATH) / case_file_name
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_yaml(test_flow_file)
        logging.info(mt_response)
        if is_bulk_run:
            rh_client = RunHistoryClient(promptflow_client._ml_client)
            run_status = rh_client.wait_for_completion(mt_response.flow_run_id).get("status", "Unknown")
            assert run_status == "Completed"
        else:
            assert mt_response.is_run_completed

    @pytest.mark.parametrize(
        "case_file_name",
        TOOL_META_TEST_CASES,
    )
    def test_meta_e2e(self, promptflow_client: PromptflowClient, case_file_name):
        test_tool_file = Path(E2E_SAMPLES_PATH) / case_file_name
        logging.info(f"running tool meta {test_tool_file}")
        mt_response = promptflow_client.submit_tool_meta_from_file(test_tool_file)

        # Update this to True to create ground truth files
        create_expected_response_files = False
        if create_expected_response_files:
            # dump expected response
            expected_file = (
                (TOOL_META_RESPONSE_PATH / f"{Path(test_tool_file).stem}_response.json").resolve().absolute()
            )
            expected_file.parent.mkdir(parents=True, exist_ok=True)
            expected_file.write_text(json.dumps(mt_response.json()))
        else:
            # load expected response and validate mt response
            expected_file = (
                (TOOL_META_RESPONSE_PATH / f"{Path(test_tool_file).stem}_response.json").resolve().absolute()
            )
            expected_response = load_json(expected_file)
            assert expected_response.items() <= mt_response.json().items()

    def test_large_result_flow_e2e(self, promptflow_client: PromptflowClient, azure_run_storage):
        test_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / "large_result_flow_run.json"
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_json(test_flow_file)
        logging.info(mt_response)
        assert mt_response.is_run_completed

        # init the run storage
        flow_id = mt_response.flow_id
        flow_run_id = mt_response.flow_run_id

        # test if the run info get stored in azure blob
        record = azure_run_storage.flow_table_client.get_entity(partition_key=flow_id, row_key=flow_run_id)
        assert record["storage_type"] == AzureStorageType.BLOB

        run_info = json.loads(record["run_info"])
        blob_client = azure_run_storage.blob_service_client.get_blob_client(
            container=run_info["container"], blob=run_info["relative_path"]
        )
        run_info_data = json.loads(blob_client.download_blob().readall())
        assert run_info_data["flow_id"] == flow_id
        assert run_info_data["run_id"] == flow_run_id
        assert run_info_data["status"] == "Completed"

    @pytest.mark.parametrize(
        "case_file_name, error_code, error_message",
        [
            ("no_inputs_failed.json", "UserError", "Inputs in the request of flow 'no_inputs' is empty."),
            (
                "wrong_openai_key_failed.json",
                "UserError",
                "OpenAI API hits AuthenticationError: Incorrect API key provided: xxxxxxx. "
                "You can find your API key at https://platform.openai.com/account/api-keys. "
                "[Error reference: https://platform.openai.com/docs/guides/error-codes/api-errors]",
            ),
        ],
    )
    def test_failure_flow_e2e(self, promptflow_client: PromptflowClient, case_file_name, error_code, error_message):
        test_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / case_file_name
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_json(test_flow_file)
        logging.info(mt_response)
        assert not mt_response.is_run_completed
        assert mt_response.flow_run_error["code"] == error_code
        assert mt_response.flow_run_error["message"] == error_message

    def test_log_metrics_for_eval_flow_in_bulk_run(self, promptflow_client: PromptflowClient):
        test_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / "simple_bulk_run_variant_eval.json"
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_json(test_flow_file)
        logging.info(mt_response)
        assert mt_response.is_run_completed

        eval_flow_run = mlflow.get_run(mt_response.eval_flow_run_id)
        assert eval_flow_run.data
        # This validation shall be replaced  Task 2486209: Enrich the metrics validation part
        assert eval_flow_run.data.metrics == {
            "score.variant_0": 90.0,
            "score.variant_1": 80.0,
            "score.variant_2": 70.0,
            "win_rate.variant_1": 0.0,
            "win_rate.variant_2": 0.0,
            "lines.completed": 2.0,
            "lines.failed": 0.0,
            "nodes.compute_relevance_scores.completed": 2.0,
            "nodes.compute_relevance_scores.failed": 0.0,
            "nodes.compare_with_baseline.completed": 2.0,
            "nodes.compare_with_baseline.failed": 0.0,
            "nodes.aggregate_variants_results.completed": 1.0,
        }

    def test_log_metrics_for_eval_flow_with_existing_runs(self, promptflow_client: PromptflowClient):
        # 1. Run a bulk test first
        test_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / "simple_bulk_run_variant.json"
        logging.info(f"running flow {test_flow_file}")
        mt_response = promptflow_client.submit_flow_by_json(test_flow_file)
        logging.info(mt_response)
        assert mt_response.is_run_completed

        # 2. Run eval flow with existing runs
        eval_flow_file = Path(E2E_FLOW_SAMPLES_PATH) / "simple_eval_flow_run.json"
        logging.info(f"running flow {test_flow_file}")
        eval_flow_response = promptflow_client.submit_flow_by_json(eval_flow_file, mt_response)
        logging.info(eval_flow_response)
        assert eval_flow_response.is_run_completed
        # This validation shall be replaced  Task 2486209: Enrich the metrics validation part
        eval_flow_run = mlflow.get_run(eval_flow_response.eval_flow_run_id)
        assert eval_flow_run.data
        assert eval_flow_run.data.metrics == {
            "score.variant_0": 90.0,
            "score.variant_1": 80.0,
            "score.variant_2": 70.0,
            "win_rate.variant_1": 0.0,
            "win_rate.variant_2": 0.0,
            "lines.completed": 2.0,
            "lines.failed": 0.0,
            "nodes.compute_relevance_scores.completed": 2.0,
            "nodes.compute_relevance_scores.failed": 0.0,
            "nodes.compare_with_baseline.completed": 2.0,
            "nodes.compare_with_baseline.failed": 0.0,
            "nodes.aggregate_variants_results.completed": 1.0,
        }
