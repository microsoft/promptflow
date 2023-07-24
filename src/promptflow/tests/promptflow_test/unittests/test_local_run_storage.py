import json
import time
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.storage.local_run_storage import LocalFlowRecords, LocalRunStorage
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info, serialize


@pytest.fixture
def local_run_storage():
    return LocalRunStorage(
        db_folder_path=str(Path(mkdtemp()) / ".test_db"),
        db_name="test.db",
    )


@pytest.fixture
def local_flow_record():
    return LocalFlowRecords(
        flow_id="dummy-flow-id",
        run_id="dummy-flow-run-id",
        source_run_id="dummy-source-run-id",
        parent_run_id=None,
        root_run_id="dummy-flow-run-id",
        run_info=None,
        start_time=datetime.utcnow(),
        end_time=None,
        name="dummy-name",
        description="dummy-description",
        status="NotStarted",
        tags=json.dumps({"tag-k": "tag-v"}),
        run_type="FlowRun",
        bulk_test_id="dummy-bulk-test-id",
        created_date=datetime.utcnow(),
        flow_graph="dummy-flow-graph",
        flow_graph_layout="dummy-flow-graph-layout",
    )


@pytest.mark.unittest
class TestLocalRunStorage:
    def test_get_flow_run_run_info_is_None(self, local_run_storage, local_flow_record):
        """Test get_flow_run when flow_run.info is None."""
        local_run_storage.flow_table_client.insert(local_flow_record)
        run_info = local_run_storage.get_flow_run(run_id="dummy-flow-run-id", flow_id="dummy-flow-id")
        assert isinstance(run_info, FlowRunInfo)
        assert run_info.run_id == local_flow_record.run_id
        assert run_info.flow_id == local_flow_record.flow_id
        assert run_info.root_run_id == local_flow_record.root_run_id
        assert run_info.parent_run_id == ""
        assert run_info.status == Status(local_flow_record.status)
        assert run_info.start_time == local_flow_record.start_time
        assert run_info.name == local_flow_record.name
        assert run_info.tags == {"tag-k": "tag-v"}
        assert run_info.description == local_flow_record.description

    def test_get_flow_run_run_info_is_not_None(self, local_run_storage, local_flow_record):
        """Test get_flow_run when flow_run.info is not None."""
        run_info_str = json.dumps(serialize(LocalRunStorage._convert_run_record_without_run_info(local_flow_record)))
        local_flow_record.run_info = run_info_str
        local_run_storage.flow_table_client.insert(local_flow_record)
        run_info = local_run_storage.get_flow_run(run_id="dummy-flow-run-id", flow_id="dummy-flow-id")
        assert isinstance(run_info, FlowRunInfo)
        assert run_info.run_id == local_flow_record.run_id
        assert run_info.flow_id == local_flow_record.flow_id
        assert run_info.root_run_id == local_flow_record.root_run_id
        assert run_info.parent_run_id == ""
        assert run_info.status == Status(local_flow_record.status)
        assert run_info.start_time == local_flow_record.start_time
        assert run_info.name == local_flow_record.name
        assert run_info.tags == {"tag-k": "tag-v"}
        assert run_info.description == local_flow_record.description

    def test_update_flow_run(self, local_run_storage, local_flow_record):
        """
        First save flow run and then update it.
        This is to test the scenario where root flow run is first saved by MT before executor.
        """
        # Save local record.
        # Sleep 1 second to make sure create time and start time are different.
        time.sleep(1)
        local_run_storage.flow_table_client.insert(local_flow_record)
        # Update local record.
        run_info = local_run_storage.get_flow_run(run_id="dummy-flow-run-id", flow_id="dummy-flow-id")
        run_info.status = Status.Running
        run_info.start_time = datetime.utcnow()
        local_run_storage.update_flow_run_info(run_info)
        # Get again and make sure fields are not missing.
        new_record: LocalFlowRecords = local_run_storage.flow_table_client.get("dummy-flow-run-id")
        assert new_record.flow_graph == local_flow_record.flow_graph
        assert new_record.flow_graph_layout == local_flow_record.flow_graph_layout
        assert new_record.bulk_test_id == local_flow_record.bulk_test_id
        assert new_record.run_type == local_flow_record.run_type
        assert new_record.name == local_flow_record.name
        assert new_record.description == local_flow_record.description
        assert new_record.tags == local_flow_record.tags
        # Assert update is effective.
        assert new_record.start_time > new_record.created_date
        assert new_record.status == Status.Running.value
        # Make sure run_info is updated.
        deserialize_flow_run_info(json.loads(new_record.run_info)) == run_info

    def test_upload_metrics(self, local_run_storage):
        metrics = {
            "accuracy": [
                {"value": 0.9, "variant_id": "variant0"},
                {"value": 0.9, "variant_id": "variant1"},
                {"value": 0.9},
            ]
        }

        retrieved_metrics = {
            "accuracy.variant0": 0.9,
            "accuracy.variant1": 0.9,
        }

        local_run_storage._upload_metrics(
            metrics, flow_run_id="dummy-flow-run-id", flow_id="dummy-flow-id", parent_run_id="dummy-parent-run-id"
        )
        # Make sure list works.
        listed_metrics = local_run_storage.metrics_client.get_by_field(parent_run_id="dummy-parent-run-id")
        assert len(listed_metrics) == 1
        assert listed_metrics[0].to_metrics() == retrieved_metrics
        # Make sure get works.
        metrics_get = local_run_storage.metrics_client.get("dummy-flow-run-id")
        assert metrics_get.to_metrics() == retrieved_metrics

    def test_cancel_run(self, local_run_storage, local_flow_record):
        run_id = "dummy-flow-run-id"
        local_run_storage.flow_table_client.insert(local_flow_record)
        # Make the run_info status as running.
        run_info = local_run_storage.get_flow_run(run_id="dummy-flow-run-id", flow_id="dummy-flow-id")
        run_info.status = Status.Running
        run_info.start_time = datetime.utcnow()
        local_run_storage.update_flow_run_info(run_info)

        local_run_storage.cancel_run(run_id)
        # Assert flow run info's status and endtime are updated.
        flow_run_info: FlowRunInfo = local_run_storage.get_flow_run(run_id)
        assert flow_run_info.status == Status.Canceled
        assert flow_run_info.end_time is not None and flow_run_info.end_time > flow_run_info.start_time
        # Assert flow run record's status and endtime are updated.
        flow_run_record: LocalFlowRecords = local_run_storage._get_flow_run_record(run_id)
        assert flow_run_record.status == Status.Canceled.value
        assert flow_run_record.end_time is not None and flow_run_record.end_time == flow_run_info.end_time

    def test_get_run_status(self, local_run_storage, local_flow_record):
        """Run status should be obtained from flow records, not flow run info."""
        run_id = "dummy-flow-run-id"
        run_info_str = json.dumps(serialize(LocalRunStorage._convert_run_record_without_run_info(local_flow_record)))
        local_flow_record.run_info = run_info_str

        # Make local_flow_record's status different from run_info's status.
        local_flow_record.status = Status.Canceled.value
        local_run_storage.flow_table_client.insert(local_flow_record)
        run_status = local_run_storage.get_run_status(run_id)

        # Run status should align with flow record's status.
        assert run_status == Status.Canceled.value
