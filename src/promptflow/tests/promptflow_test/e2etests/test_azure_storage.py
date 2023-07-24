import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import mlflow
import pytest
from mlflow.entities.run_status import RunStatus as MlflowRunStatus
from mlflow.exceptions import RestException
from mlflow.protos.databricks_pb2 import RESOURCE_DOES_NOT_EXIST, ErrorCode
from pytest_mock import MockFixture

from promptflow._constants import AzureStorageType
from promptflow.contracts.flow import BatchFlowRequest, EvalRequest
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.exceptions import ErrorTarget, RootErrorCode, UserErrorException, ValidationException
from promptflow.storage.azureml_run_storage import AzureMLRunStorage
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info, deserialize_node_run_info
from promptflow_test.utils import assert_success, load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


@pytest.mark.usefixtures("use_secrets_config_file", "set_azureml_config", "basic_executor")
@pytest.mark.e2etest
@pytest.mark.flaky(reruns=3, reruns_delay=1)
class TestAzureStorage:
    def test_write_record_to_table(self, basic_executor) -> None:
        """Test write flow/node records to remote azure table."""
        json_file = Path(JSON_DATA_ROOT) / "dummy_flow.json"
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        # assert run storage type
        run_storage = basic_executor._run_tracker._storage
        assert isinstance(run_storage, AzureMLRunStorage)

        #  Currently the MiddleTier service will create the root run before submitting the request
        #  Here we create the root run manually to simulate the behavior
        flow_table = run_storage.flow_table_client
        created_entity = {
            "name": "Some dummy name which is not in request",
            "PartitionKey": request_data.flow_id,
            "RowKey": request_data.flow_run_id,
            "root_run_id": request_data.flow_run_id,
            "status": "NotStarted",
        }

        flow_table.create_entity(created_entity)
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # assert flow info and node info gets recorded in remote azure table
        flow_id = result["flow_runs"][0]["flow_id"]
        flow_run_id = result["flow_runs"][0]["run_id"]
        node_run_id = result["node_runs"][0]["run_id"]

        flow_record = run_storage.flow_table_client.get_entity(partition_key=flow_id, row_key=flow_run_id)
        assert flow_record["run_info"]  # Should have value
        assert flow_record["storage_type"] == AzureStorageType.TABLE
        assert flow_record["name"] == created_entity["name"]  # Should not be updated
        assert flow_record["status"] == "Completed"  # Should be updated
        assert isinstance(flow_record["end_time"], datetime)
        assert isinstance(flow_record["start_time"], datetime)

        node_record = run_storage.node_table_client.get_entity(partition_key=flow_run_id, row_key=node_run_id)
        assert node_record["run_info"]
        assert node_record["storage_type"] == AzureStorageType.TABLE

    @pytest.mark.parametrize(
        "file_name",
        [
            "../e2e_samples/large_result_flow.json",
            # "large_result_flow_500_inputs.json",  # this is for stress testing, do not enable this in CI
        ],
    )
    def test_write_record_to_blob(self, basic_executor, file_name) -> None:
        """Test write flow/node records to remote azure blob."""

        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # assert run storage type
        run_storage = basic_executor._run_tracker._storage
        assert isinstance(run_storage, AzureMLRunStorage)

        # 1. assert flow info and node info gets partially recorded in remote azure table
        flow_id = result["flow_runs"][0]["flow_id"]
        flow_run_id = result["flow_runs"][0]["run_id"]
        node_run_id = result["node_runs"][0]["run_id"]

        flow_record = run_storage.flow_table_client.get_entity(partition_key=flow_id, row_key=flow_run_id)
        assert flow_record["storage_type"] == AzureStorageType.BLOB
        run_info_data = json.loads(flow_record["run_info"])
        relative_path = f"{run_storage.FLOW_BLOB_PATH_PREFIX}/{flow_id}/{flow_run_id}.json"
        assert run_info_data == {
            "container": run_storage.BLOB_CONTAINER_NAME,
            "relative_path": relative_path,
        }
        print(f"Created blob flow run info: {run_info_data}")

        node_record = run_storage.node_table_client.get_entity(partition_key=flow_run_id, row_key=node_run_id)
        assert node_record["storage_type"] == AzureStorageType.BLOB
        run_info_data = json.loads(node_record["run_info"])
        relative_path = f"{run_storage.NODE_BLOB_PATH_PREFIX}/{flow_run_id}/{node_run_id}.json"
        assert run_info_data == {
            "container": run_storage.BLOB_CONTAINER_NAME,
            "relative_path": relative_path,
        }
        print(f"Created blob node run info: {run_info_data}")

        # 2. assert flow info and node info get fully recorded in remote azure blob

        # test flow run
        partition_key = flow_id
        row_key = flow_run_id
        blob_path = f"{run_storage.FLOW_BLOB_PATH_PREFIX}/{partition_key}/{row_key}.json"
        blob_client = run_storage.blob_service_client.get_blob_client(
            container=run_storage.BLOB_CONTAINER_NAME, blob=blob_path
        )
        run_info_data = json.loads(blob_client.download_blob().readall())
        flow_run_info = deserialize_flow_run_info(run_info_data)
        assert flow_run_info.run_id == flow_run_id

        # test node run
        partition_key = flow_run_id
        row_key = node_run_id
        blob_path = f"{run_storage.NODE_BLOB_PATH_PREFIX}/{partition_key}/{row_key}.json"
        blob_client = run_storage.blob_service_client.get_blob_client(
            container=run_storage.BLOB_CONTAINER_NAME, blob=blob_path
        )
        run_info_data = json.loads(blob_client.download_blob().readall())
        node_run_info = deserialize_node_run_info(run_info_data)
        assert node_run_info.run_id == node_run_id

    def test_log_metrics_in_evaluation_flow_in_bulk_test(self, basic_executor):
        # get request json
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_with_variants_and_eval.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)

        # change bulk test id and eval_flow_run_id
        bulk_test_id = str(uuid.uuid4())
        eval_flow_run_id = str(uuid.uuid4())
        refine_bulk_test_raw_request(raw_request, bulk_test_id=bulk_test_id, eval_flow_run_id=eval_flow_run_id)
        result = basic_executor.exec_request_raw(raw_request=raw_request, raise_ex=True)

        # assert result
        assert_success(result)
        evaluation_result = result["evaluation"]
        assert_success(evaluation_result)

        # assert metrics in eval run, aml run id will be evaluation_result
        finished_run = mlflow.get_run(eval_flow_run_id)
        assert finished_run.data
        assert finished_run.data.metrics == {
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

        # assert bulk test run status
        bulk_test_run = mlflow.get_run(bulk_test_id)
        assert bulk_test_run.info.status == MlflowRunStatus.to_string(MlflowRunStatus.FINISHED)

    def test_log_metrics_in_evaluation_flow_with_existing_runs(self, basic_executor):
        # 1. Run a bulk test first
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_with_variants.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)

        # set bulk test id and non-base variant run ids
        bulk_test_id = str(uuid.uuid4())
        base_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id)

        # run bulk test and check result
        result = basic_executor.exec_request_raw(raw_request, raise_ex=True)
        assert_success(result)

        # assert bulk test run status
        bulk_test_run = mlflow.get_run(bulk_test_id)
        assert bulk_test_run.info.status == "FINISHED"

        # 2. Run eval flow with existing runs
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_eval_flow_existing_runs.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.Eval)
        eval_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(
            raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id, eval_flow_run_id=eval_flow_run_id
        )

        # execute the request with eval mode
        result = basic_executor.exec_request_raw(raw_request, raise_ex=True)
        assert_success(result)

        # assert metrics in eval run, aml run id will be evaluation_result
        finished_run = mlflow.get_run(eval_flow_run_id)
        assert finished_run.data
        assert finished_run.data.metrics == {
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

    def test_eval_flow_but_with_normal_flow_run_mode(self, basic_executor):
        json_file = Path(JSON_DATA_ROOT) / "../e2e_samples/QnA_relevance_scores.json"
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        assert_success(result)

        # assert there is no aml run created
        try:
            mlflow.get_run(request_data.flow_run_id)
        except Exception as e:
            assert isinstance(e, RestException)
            assert e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)

    def test_cancel_aml_root_run(self, basic_executor):
        # cancel an active run
        run_id = str(uuid.uuid4())
        mlflow_helper = basic_executor._run_tracker._storage._mlflow_helper
        mlflow_helper.create_run(run_id=run_id, start_after_created=False)
        basic_executor._run_tracker._storage.cancel_run(run_id=run_id)
        finished_run = mlflow.get_run(run_id)
        assert finished_run.info.status == MlflowRunStatus.to_string(MlflowRunStatus.KILLED)

        # test ending a canceled run, should not raise error
        mlflow_helper.start_run(run_id=run_id)
        mlflow_helper.end_run(run_id=run_id, status="Completed")

        # cancel an completed run, should not raise error
        run = mlflow.start_run()
        run_id = run.info.run_id
        mlflow.end_run()
        basic_executor._run_tracker._storage.cancel_run(run_id=run_id)
        finished_run = mlflow.get_run(run_id)
        assert finished_run.info.status == MlflowRunStatus.to_string(MlflowRunStatus.FINISHED)

        # test get run status
        run_status = basic_executor._run_tracker._storage.get_run_status(run_id=run_id)
        assert run_status == "Completed"

    def test_write_error_message_to_run_history(self, basic_executor, mocker: MockFixture):
        # mock flow execution to raise error
        test_error_msg = "Test user error"
        mocker.patch(
            "promptflow.executor.flow_executor.FlowExecutor._exec",
            side_effect=UserErrorException(message=test_error_msg, target=ErrorTarget.AZURE_RUN_STORAGE),
        )

        json_file = Path(JSON_DATA_ROOT) / "flow_with_eval.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)

        bulk_test_id = str(uuid.uuid4())
        base_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id)

        result = basic_executor.exec_request_raw(raw_request)
        assert result["flow_runs"][0]["status"] == "Failed"
        assert result["flow_runs"][0]["error"]["message"] == test_error_msg

        # assert base flow aml run failed with specified error message. mlflow run info has no error info so we
        # use ml client to get run info here
        ml_client = basic_executor._run_tracker._storage._ml_client
        base_flow_run = ml_client.jobs._runs_operations.get_run(run_id=base_flow_run_id)
        assert base_flow_run.status == "Failed"
        assert base_flow_run.error.error.code == "UserError"
        assert base_flow_run.error.error.message == test_error_msg

        # assert bulk test aml run with completed status
        bulk_test_run = mlflow.get_run(run_id=bulk_test_id)
        assert bulk_test_run.info.status == MlflowRunStatus.to_string(MlflowRunStatus.FINISHED)

    def test_write_properties_to_run_history(self, basic_executor):
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_with_variants_and_eval.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)

        bulk_test_id = str(uuid.uuid4())
        base_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id)

        result = basic_executor.exec_request_raw(raw_request)
        assert_success(result)

        ml_client = basic_executor._run_tracker._storage._ml_client

        # root runs has variant_run_id + eval_flow_run_id
        # Verify variant + eval run have properties(total_tokens etc)
        root_runs = raw_request.get_root_run_ids()
        for run_id in root_runs:
            run_dto = ml_client.jobs._runs_operations.get_run(run_id=run_id)
            assert run_dto.properties == {
                "azureml.promptflow.total_child_runs": "2",
                "azureml.promptflow.total_tokens": "0",
            }

        # Verify bulk run not have properties(total_tokens etc)
        bulk_test_run = ml_client.jobs._runs_operations.get_run(run_id=bulk_test_id)
        assert bulk_test_run.properties == {}

    def test_mark_not_started_aml_root_runs_as_failed(self, basic_executor):
        # get request json
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_flow_with_validation_fails.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)

        # change bulk test id and eval_flow_run_id
        bulk_test_id = str(uuid.uuid4())
        flow_id = raw_request.flow_id
        refine_bulk_test_raw_request(raw_request, bulk_test_id=bulk_test_id)
        root_runs = raw_request.get_root_run_ids()

        run_tracker = basic_executor._run_tracker
        # mock MT behavior to create run info in table before execution
        for run_id in root_runs:
            run_info = FlowRunInfo(
                flow_id=flow_id,
                run_id=run_id,
                root_run_id=run_id,
                parent_run_id=bulk_test_id,
                status=Status.NotStarted,
                error=None,
                inputs=None,
                output=None,
                metrics=None,
                request=None,
                source_run_id=None,
                start_time=None,
                end_time=None,
            )
            run_tracker.persist_flow_run(run_info)

        error_msg = "Input 'question' in line 0 is not provided"
        with pytest.raises(ValidationException, match=error_msg):
            basic_executor.exec_request_raw(raw_request=raw_request)

        ml_client = basic_executor._run_tracker._storage._ml_client
        for run_id in root_runs:
            # assert status and error message in run history
            ml_client_run = ml_client.jobs._runs_operations.get_run(run_id=run_id)
            assert ml_client_run.status == "Failed"
            assert error_msg in ml_client_run.error.error.message

            # assert status and error message in table
            run_info = run_tracker._storage.get_flow_run(run_id=run_id, flow_id=flow_id)
            assert run_info.status == Status.Failed
            assert error_msg in run_info.error["message"]

        # assert bulk test run status
        ml_client_run = ml_client.jobs._runs_operations.get_run(run_id=bulk_test_id)
        assert ml_client_run.status == Status.Completed.value

    def test_aggregate_child_run_errors(self, basic_executor):
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_with_failed_child_run.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)
        ml_client = basic_executor._run_tracker._storage._ml_client

        bulk_test_id = str(uuid.uuid4())
        base_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id)

        basic_executor.exec_request_raw(raw_request)

        # assert root run status
        ml_client_run = ml_client.jobs._runs_operations.get_run(run_id=base_flow_run_id)
        assert ml_client_run.status == Status.Completed.value
        assert ml_client_run.error.error.code == RootErrorCode.SYSTEM_ERROR
        assert ml_client_run.error.error.reference_code == ErrorTarget.AZURE_RUN_STORAGE
        assert json.loads(ml_client_run.error.error.message_format) == {
            "totalChildRuns": 3,
            "userErrorChildRuns": 1,
            "systemErrorChildRuns": 1,
            "errorDetails": [
                {"code": "UserError/ValidationError", "messageFormat": "", "count": 1},
                {"code": "SystemError/AzureStorageOperationError", "messageFormat": "", "count": 1},
            ],
        }

    @pytest.mark.skip("Stress testing, just enable when needed.")
    def test_aggregate_child_run_errors_stress_testing(self, basic_executor):
        """
        Stress testing, 500 child runs and each run has error message format with length 5000, total length of
        aggregated root run's messageFormat should be over 1.6 million characters and we truncated it to half the size.
        """
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests/simple_bulk_test_with_failed_child_run_500_inputs.json"
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)
        ml_client = basic_executor._run_tracker._storage._ml_client

        bulk_test_id = str(uuid.uuid4())
        base_flow_run_id = raw_request.flow_run_id
        refine_bulk_test_raw_request(raw_request, base_flow_run_id=base_flow_run_id, bulk_test_id=bulk_test_id)

        basic_executor.exec_request_raw(raw_request)

        # assert root run status
        ml_client_run = ml_client.jobs._runs_operations.get_run(run_id=base_flow_run_id)
        assert ml_client_run.status == Status.Completed.value
        assert ml_client_run.error.error.code == RootErrorCode.SYSTEM_ERROR
        assert ml_client_run.error.error.reference_code == ErrorTarget.AZURE_RUN_STORAGE
        assert len(ml_client_run.error.error.message_format) > 800000


def refine_bulk_test_raw_request(
    raw_request: SubmitFlowRequest, base_flow_run_id=None, bulk_test_id=None, eval_flow_run_id=None
):
    """Refine bulk test raw request, fill ids in the request"""
    base_flow_run_id = base_flow_run_id or raw_request.flow_run_id
    bulk_test_id = bulk_test_id or str(uuid.uuid4())
    eval_flow_run_id = eval_flow_run_id or str(uuid.uuid4())
    print(
        f"bulk_test_id: {bulk_test_id!r}, "
        f"base_flow_run_id: {base_flow_run_id!r}."
        f"eval_flow_run_id: {eval_flow_run_id!r}, "
    )

    root_run_ids = {
        "bulk_test_id": bulk_test_id,
        "base_flow_run_id": base_flow_run_id,
        "eval_flow_run_id": eval_flow_run_id,
    }

    # specify the bulk test id and existing run ids
    submission_data = raw_request.submission_data
    if isinstance(submission_data, BatchFlowRequest):
        if submission_data.bulk_test_id:
            submission_data.bulk_test_id = bulk_test_id
        if submission_data.eval_flow_run_id:
            submission_data.eval_flow_run_id = eval_flow_run_id
        # for bulk test with variants and eval
        if submission_data.variants_runs:
            submission_data.variants_runs = {
                "variant_1": f"{base_flow_run_id}_{bulk_test_id}_variant_1",
                "variant_2": f"{base_flow_run_id}_{bulk_test_id}_variant_2",
            }
            root_run_ids.update(submission_data.variants_runs)

    # for eval with existing runs
    if isinstance(submission_data, EvalRequest):
        if submission_data.bulk_test_flow_run_ids:
            submission_data.bulk_test_flow_run_ids = [
                base_flow_run_id,  # variant 0 run id is base flow run id
                f"{base_flow_run_id}_{bulk_test_id}_variant_1",
                f"{base_flow_run_id}_{bulk_test_id}_variant_2",
            ]

    return root_run_ids
