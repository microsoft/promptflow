import uuid
from datetime import datetime
from pathlib import Path

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.storage.local_run_storage import LocalFlowRecords, LocalRunStorage
from promptflow_test.e2etests.test_executor import assert_run_ids, assert_runs_persisted
from promptflow_test.utils import _save_result_in_temp_folder, assert_success, load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"


def store_root_flow_run_record(flow_id: str, flow_run_id: str, source_run_id: str, local_storage: LocalRunStorage):
    local_record = LocalFlowRecords(
        flow_id=flow_id,
        run_id=flow_run_id,
        source_run_id=source_run_id,
        parent_run_id=None,
        root_run_id=flow_run_id,
        run_info=None,
        start_time=datetime.utcnow(),
        end_time=None,
        name="dummy-name",
        description="dummy-description",
        status="NotStarted",
        tags="dummy-tags",
        run_type="FlowRun",
        bulk_test_id=None,
        created_date=datetime.utcnow(),
        flow_graph=None,
        flow_graph_layout=None,
    )

    local_storage.flow_table_client.insert(local_record)


@pytest.mark.usefixtures("use_secrets_config_file", "local_executor")
@pytest.mark.e2etest
@pytest.mark.flaky(reruns=3, reruns_delay=1)
class TestLocalExecutor:
    @pytest.mark.parametrize(
        "file_name",
        [
            "example_flow.json",
            "batch_request_e2e.json",
            "qa_with_bing.json",
            "eval_flow.json",
        ],
    )
    def test_flow_run(self, local_executor, file_name):
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)

        result = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        result_file = _save_result_in_temp_folder(result, file_name)

        assert_success(result, result_file)
        assert_run_ids(result)
        assert_runs_persisted(local_executor._run_tracker._storage, result)

    def test_root_flow_run_created_first(self, local_executor):
        """Test the scenario where root flow run is first created in SMT before executor."""
        file_name = "example_flow.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        store_root_flow_run_record(
            flow_id=request_data.flow_id,
            flow_run_id=request_data.flow_run_id,
            source_run_id=request_data.source_flow_run_id,
            local_storage=local_executor._run_tracker._storage,
        )
        result = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        result_file = _save_result_in_temp_folder(result, file_name)

        assert_success(result, result_file)
        assert_run_ids(result)
        assert_runs_persisted(local_executor._run_tracker._storage, result)

    def test_variants_flow_with_eval_collection(self, local_executor):
        file_name = "variants_flow_with_eval_collection.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest
        )

        # Change bulk test id and eval_flow_run_id.
        request = request_data.submission_data
        eval_flow_run_id = str(uuid.uuid4())
        bulk_test_run_id = str(uuid.uuid4())
        request.bulk_test_id = bulk_test_run_id
        request.eval_flow_run_id = eval_flow_run_id

        # Set variant run ids.
        variant_run_1_id = str(uuid.uuid4())
        variant_run_2_id = str(uuid.uuid4())
        request.variants_runs["variant1"] = variant_run_1_id
        request.variants_runs["variant2"] = variant_run_2_id

        # Mimic MT service's behavior and save root flow run.
        root_flow_run_ids = [
            request_data.flow_run_id,
            variant_run_1_id,
            variant_run_2_id,
            eval_flow_run_id,
        ]
        for run_id in root_flow_run_ids:
            store_root_flow_run_record(
                flow_id=request_data.flow_id,
                flow_run_id=run_id,
                source_run_id=request_data.source_flow_run_id,
                local_storage=local_executor._run_tracker._storage,
            )

        result = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        evaluation_result = result.pop("evaluation")
        # Check bulk run.
        assert_success(result)
        assert_run_ids(result, variants_count=2, bulk_test_id=bulk_test_run_id)
        # Check evaluation run.
        assert_success(evaluation_result)
        assert_run_ids(evaluation_result, bulk_test_id=bulk_test_run_id)

        # Assert metrics in eval run.
        local_metrics = local_executor._run_tracker._storage.metrics_client.get(eval_flow_run_id)
        assert len(local_metrics.to_metrics().keys()) > 0
        assert local_metrics.parent_run_id == bulk_test_run_id

        # Assert list metrics by bulk_test_run_id works.
        local_metrics_list = local_executor._run_tracker._storage.metrics_client.get_by_field(
            parent_run_id=bulk_test_run_id
        )
        assert len(local_metrics_list) == 1
