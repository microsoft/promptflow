import json
import logging
import os
import uuid
from pathlib import Path

import pytest
from azureml._restclient.snapshots_client import SnapshotsClient
from azureml.core import Workspace
from requests import HTTPError

from promptflow._constants import AzureStorageType
from promptflow.contracts.run_mode import RunMode
from promptflow.exceptions import ErrorTarget
from promptflow.runtime.client import _execute
from promptflow_test.e2etests.test_samples import BUILTIN_SAMPLE_BULK_TESTS, BUILTIN_SAMPLE_FLOW_RUNS
from promptflow_test.run_test_utils import FlowRequestService, assert_result_valid
from promptflow_test.utils import assert_success, ensure_request_file

TEST_ROOT = Path(__file__) / "../.."
JSON_DATA_ROOT = TEST_ROOT / "test_configs/e2e_samples"

E2E_SNAPSHOT_ROOT = JSON_DATA_ROOT / "e2e_snapshots"
BULKTEST_SNAPSHOT = ["llm_tools", "prompt_tools", "script_with_import"]


def prt_execute_flow(flow_path: str, prt_execute_config: dict):
    flow_path = str(flow_path)
    return _execute(
        input_file=flow_path,
        key=prt_execute_config["endpoint_key"],
        url=prt_execute_config["endpoint_url"],
        deployment=prt_execute_config["deployment_name"],
        connection_file=prt_execute_config["connection_file_path"],
        dump_logs=False,
    )


def upload_snapshot(deployment_model_config, folder_path):
    model_config = deployment_model_config["deployment"]
    workspace = Workspace.get(
        name=model_config["workspace_name"],
        subscription_id=model_config["subscription_id"],
        resource_group=model_config["resource_group"],
    )
    snapshot_client = SnapshotsClient(workspace.service_context)
    return snapshot_client.create_snapshot(folder_path)


def construct_request_file(snapshot_folder, snapshot_id):
    inputs_file = snapshot_folder / "inputs.json"
    inputs = []
    with open(inputs_file, "r") as f:
        inputs.append(json.load(f))
    request = {
        "batch_inputs": inputs,
        "bulk_test_id": str(uuid.uuid4()),
        "baseline_variant_id": "variant_0",
        "flow_source": {
            "flow_source_type": 1,
            "flow_source_info": {"snapshot_id": snapshot_id},
            "flow_dag_file": "flow.dag.yaml",
        },
    }
    request_file = snapshot_folder / "request.json"
    request_file.write_text(json.dumps(request))
    return request_file


@pytest.mark.endpointtest
class TestEndpoint:
    @pytest.mark.parametrize(
        "folder_name",
        BULKTEST_SNAPSHOT,
    )
    def test_executor_bulktest_with_snapshot(
        self, ml_client, deployment_model_config, prt_execute_config, folder_name
    ) -> None:
        snapshot_folder = Path(JSON_DATA_ROOT) / folder_name
        snapshot_folder = snapshot_folder.resolve().absolute()
        snapshot_id = upload_snapshot(deployment_model_config, snapshot_folder)
        req_file = construct_request_file(snapshot_folder, snapshot_id)
        with open(req_file, "r") as f:
            request = json.load(f)
        try:
            result = prt_execute_flow(req_file, prt_execute_config)
        finally:
            os.remove(req_file)

        assert_result_valid(
            request=request,
            response=result,
            request_service=FlowRequestService.RUNTIME,
            mode=RunMode.BulkTest,
            ml_client=ml_client,
        )

    @pytest.mark.parametrize(
        "file_name",
        BUILTIN_SAMPLE_FLOW_RUNS,
    )
    def test_executor_flow_run(self, ml_client, prt_execute_config, file_name) -> None:
        req_file = Path(JSON_DATA_ROOT) / file_name
        req_file = req_file.resolve().absolute()
        req_file = ensure_request_file(req_file)
        with open(req_file, "r") as f:
            request = json.load(f)
        result = prt_execute_flow(req_file, prt_execute_config)
        assert_result_valid(
            request=request,
            response=result,
            request_service=FlowRequestService.RUNTIME,
            mode=RunMode.Flow,
            ml_client=ml_client,
        )

    @pytest.mark.parametrize(
        "file_name",
        BUILTIN_SAMPLE_BULK_TESTS,
    )
    def test_executor_bulktest(self, prt_execute_config, azure_run_storage, ml_client, file_name) -> None:
        req_file = Path(JSON_DATA_ROOT) / file_name
        req_file = req_file.resolve().absolute()
        req_file = ensure_request_file(req_file)
        with open(req_file, "r") as f:
            request = json.load(f)
        request["bulk_test_id"] = str(uuid.uuid4())
        request["baseline_variant_id"] = "variant_0"
        new_file_name = file_name.replace(".json", "_new.json")
        flow_file_path_new = str((Path(JSON_DATA_ROOT) / new_file_name).resolve().absolute())
        with open(flow_file_path_new, "w") as write_file:
            write_file.write(json.dumps(request))
        try:
            result = prt_execute_flow(Path(JSON_DATA_ROOT) / new_file_name, prt_execute_config)
        finally:
            os.remove(flow_file_path_new)

        assert_result_valid(
            request=request,
            response=result,
            request_service=FlowRequestService.RUNTIME,
            mode=RunMode.BulkTest,
            ml_client=ml_client,
        )

    def test_large_result_flow(self, ml_client, prt_execute_config, azure_run_storage):
        flow_file_path = Path(JSON_DATA_ROOT) / "large_result_flow.json"
        req_file = flow_file_path.resolve().absolute()
        req_file = ensure_request_file(req_file)
        with open(req_file, "r") as f:
            request = json.load(f)
        result = prt_execute_flow(flow_file_path, prt_execute_config)
        assert_success(result)

        # init the run storage
        run_storage = azure_run_storage
        flow_id = result["flow_runs"][0]["flow_id"]
        flow_run_id = result["flow_runs"][0]["run_id"]

        # test if the run info get stored in azure blob
        record = run_storage.flow_table_client.get_entity(partition_key=flow_id, row_key=flow_run_id)
        assert record["storage_type"] == AzureStorageType.BLOB

        run_info = json.loads(record["run_info"])
        blob_client = run_storage.blob_service_client.get_blob_client(
            container=run_info["container"], blob=run_info["relative_path"]
        )
        run_info_data = json.loads(blob_client.download_blob().readall())
        assert run_info_data["flow_id"] == flow_id
        assert run_info_data["run_id"] == flow_run_id
        assert run_info_data["status"] == "Completed"
        assert_result_valid(
            request=request,
            response=result,
            request_service=FlowRequestService.RUNTIME,
            mode=RunMode.Flow,
            ml_client=ml_client,
        )

    def test_e2e_failures(self, prt_execute_config):
        """An invalide case to verify the error handling logic."""
        flow_file_path = TEST_ROOT / "test_configs/executor_wrong_requests/no_input.json"
        with pytest.raises(HTTPError) as exc_info:
            prt_execute_flow(flow_file_path, prt_execute_config)

        ex = exc_info.value.response.json().get("error")
        assert ex.get("message") == "Inputs in the request of flow 'dummy_qna' is empty."
        assert ex.get("code") == "UserError"
        assert ex.get("referenceCode") == ErrorTarget.EXECUTOR

    @pytest.mark.skip("Skipped until the endpoint with log_metric is deployed.")
    def test_log_metrics_in_evaluation_flow(self, prt_execute_config):
        file_name = "flow_with_eval.json"
        flow_file_path = Path(JSON_DATA_ROOT) / "../executor_api_requests" / file_name
        flow_file_path = str(flow_file_path.resolve().absolute())
        with open(flow_file_path, "r") as f:
            request = json.load(f)
        bulk_test_run_id = str(uuid.uuid4())
        eval_flow_run_id = str(uuid.uuid4())
        logging.info(f"bulk_test_id: {bulk_test_run_id!r}, eval_flow_run_id: {eval_flow_run_id!r}")
        request["bulk_test_id"] = bulk_test_run_id
        request["eval_flow_run_id"] = eval_flow_run_id
        flow_file_path_new = flow_file_path.replace(".json", "_new.json")
        with open(flow_file_path_new, "w") as write_file:
            write_file.write(json.dumps(request))
        try:
            result = prt_execute_flow(flow_file_path_new, prt_execute_config)
        finally:
            os.remove(flow_file_path_new)

        assert_success(result)
