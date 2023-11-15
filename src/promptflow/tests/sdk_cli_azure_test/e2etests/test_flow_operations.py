# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import uuid
from pathlib import Path

import pytest

from promptflow._sdk._constants import FlowType
from promptflow._sdk._errors import FlowOperationError
from promptflow.azure import PFClient

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestFlow:
    def test_create_flow(self, pf: PFClient):
        flow_source = flow_test_dir / "simple_fetch_url/"
        flow_display_name = f"{flow_source.name}_{uuid.uuid4()}"
        description = "test flow"
        tags = {"owner": "sdk"}
        result = pf.flows.create_or_update(
            flow=flow_source, display_name=flow_display_name, type=FlowType.STANDARD, description=description, tags=tags
        )
        remote_flow_dag_path = result.path

        # make sure the flow is created successfully
        assert pf.flows._storage_client._check_file_share_file_exist(remote_flow_dag_path) is True
        assert result.display_name == flow_display_name
        assert result.type == FlowType.STANDARD
        assert result.tags == tags
        assert result.path.endswith(f"/promptflow/{flow_display_name}/flow.dag.yaml")

    def test_flow_test_with_config(self, remote_workspace_resource_id):
        from promptflow import PFClient

        client = PFClient(config={"connection.provider": remote_workspace_resource_id})
        output = client.test(flow=flow_test_dir / "web_classification")
        assert output.keys() == {"category", "evidence"}

    def test_list_flows(self, remote_client):
        flows = remote_client.flows.list(max_results=3)
        for flow in flows:
            print(json.dumps(flow._to_dict(), indent=4))
        assert len(flows) == 3

    def test_list_flows_invalid_cases(self, remote_client):
        with pytest.raises(FlowOperationError, match="'max_results' must be a positive integer"):
            remote_client.flows.list(max_results=0)

        with pytest.raises(FlowOperationError, match="'flow_type' must be one of"):
            remote_client.flows.list(flow_type="unknown")

        with pytest.raises(FlowOperationError, match="Invalid list view type"):
            remote_client.flows.list(list_view_type="invalid")
