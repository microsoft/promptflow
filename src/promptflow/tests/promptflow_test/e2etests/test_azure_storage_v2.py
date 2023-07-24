import logging
import sys
from pathlib import Path

import pytest

from promptflow.storage.azureml_run_storage_v2 import AzureMLRunStorageV2
from promptflow_test.utils import (
    get_executor_with_azure_storage_v2,
    load_and_convert_to_raw,
    read_json_or_jsonl_from_blob,
)

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"
FLOW_ARTIFACTS_PATH_PREFIX = "promptflow/PromptFlowArtifacts"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


def _validate_flow_artifacts(blob_client, input_counts):
    """Validate the folder: flow_artifacts"""
    # Assert the flow_artifacts contains {:09}_{:09}.jsonl file
    # Assert each line in the flow_artifacts_file contains keys: "line_number", "run_info"
    flow_artifacts = read_json_or_jsonl_from_blob(blob_client)
    assert all({"line_number", "run_info"}.issubset(flow_artifact.keys()) for flow_artifact in flow_artifacts)
    # Assert the lines in the flow_artifacts_file should be equal to inputs count
    assert len(flow_artifacts) == input_counts
    logging.info("The validation of flow_artifacts is passed.")


@pytest.mark.usefixtures("use_secrets_config_file", "set_azureml_config")
@pytest.mark.e2etest
class TestAzureStorageV2:
    def test_write_record_to_blob(self) -> None:
        """Test write flow/node records to remote azure blob."""
        json_file = Path(JSON_DATA_ROOT) / "dummy_flow.json"
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        input_line_count = len(request_data.submission_data.batch_inputs)
        # assert run storage type
        executor = get_executor_with_azure_storage_v2(request_data.flow_run_id)
        run_storage = executor._run_tracker._storage
        assert isinstance(run_storage, AzureMLRunStorageV2)

        flow_run_id = request_data.flow_run_id
        print(f"flow_run_id = {flow_run_id}")

        # Start root run since executor doesn't start root run for non-batch run,
        # we manually start one for test only
        run_storage._start_aml_root_run(flow_run_id)
        executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        container_client = run_storage.blob_container_client
        bulk_run_folder_path = f"{FLOW_ARTIFACTS_PATH_PREFIX}/{flow_run_id}"
        actual_files = [blob.name for blob in container_client.list_blobs(name_starts_with=bulk_run_folder_path)]

        flow_artifacts_folder_name = run_storage.FLOW_ARTIFACTS_FOLDER_NAME
        node_artifacts_folder_name = run_storage.NODE_ARTIFACTS_FOLDER_NAME
        bulk_run_info_file = f"{bulk_run_folder_path}/run_info.json"
        flow_artifact_file = f"{bulk_run_folder_path}/{flow_artifacts_folder_name}/000000000_000000024.jsonl"

        node_artifact_file_list = []
        for node in request_data.submission_data.flow.nodes:
            for i in range(len(request_data.submission_data.batch_inputs)):
                node_artifact_file_list.append(
                    f"{bulk_run_folder_path}/{node_artifacts_folder_name}/{node.name}/{i:09d}.jsonl"
                )

        assert bulk_run_info_file in actual_files
        assert flow_artifact_file in actual_files
        assert set(node_artifact_file_list).issubset(set(actual_files))
        _validate_flow_artifacts(container_client.get_blob_client(flow_artifact_file), input_line_count)

    def test_eval_flow(self) -> None:
        """Test write flow/node records to remote azure blob."""
        json_file = JSON_DATA_ROOT / "eval_flow.json"
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        # assert run storage type
        executor = get_executor_with_azure_storage_v2(request_data.flow_run_id)
        run_storage = executor._run_tracker._storage
        assert isinstance(run_storage, AzureMLRunStorageV2)

        flow_run_id = request_data.flow_run_id
        print(f"flow_run_id = {flow_run_id}")

        # Start root run since executor doesn't start root run for non-batch run,
        # we manually start one for test only
        run_storage._start_aml_root_run(flow_run_id)
        executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        container_client = run_storage.blob_container_client
        bulk_run_folder_path = f"{FLOW_ARTIFACTS_PATH_PREFIX}/{flow_run_id}"
        actual_files = [blob.name for blob in container_client.list_blobs(name_starts_with=bulk_run_folder_path)]

        flow_artifacts_folder_name = run_storage.FLOW_ARTIFACTS_FOLDER_NAME
        node_artifacts_folder_name = run_storage.NODE_ARTIFACTS_FOLDER_NAME
        bulk_run_info_file = f"{bulk_run_folder_path}/run_info.json"
        flow_artifact_file = f"{bulk_run_folder_path}/{flow_artifacts_folder_name}/000000000_000000024.jsonl"

        node_artifact_file_list = []
        for node in request_data.submission_data.flow.nodes:
            if node.reduce:
                node_artifact_file_list.append(
                    f"{bulk_run_folder_path}/{node_artifacts_folder_name}/{node.name}/{0:09d}.jsonl"
                )
            else:
                for i in range(len(request_data.submission_data.batch_inputs)):
                    node_artifact_file_list.append(
                        f"{bulk_run_folder_path}/{node_artifacts_folder_name}/{node.name}/{i:09d}.jsonl"
                    )

        assert bulk_run_info_file in actual_files
        assert flow_artifact_file in actual_files
        assert set(node_artifact_file_list).issubset(set(actual_files))
