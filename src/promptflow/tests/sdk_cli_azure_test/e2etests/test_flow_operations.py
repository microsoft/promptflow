# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from pathlib import Path
from typing import Callable

import pytest

from promptflow._sdk._constants import FlowType
from promptflow._sdk._errors import FlowOperationError

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD
from ..recording_utilities import is_live

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


def create_flow(pf, display_name):
    flow_display_name = display_name
    flow_source = flow_test_dir / "simple_fetch_url/"
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
    return result


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
class TestFlow:
    def test_create_flow(self, pf, randstr: Callable[[str], str]):
        flow_display_name = randstr("flow_display_name")
        create_flow(pf, flow_display_name)

    def test_get_flow(self, pf, randstr: Callable[[str], str]):
        flow_display_name = randstr("flow_display_name")
        flow = create_flow(pf, flow_display_name)
        result = pf.flows.get(name=flow.name)

        # assert created flow is the same as the one retrieved
        attributes = vars(result)
        for attr in attributes:
            assert getattr(result, attr) == getattr(flow, attr), f"Assertion failed for attribute: {attr!r}"

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="Complicated test combining `pf flow test` and global config",
    )
    def test_flow_test_with_config(self, remote_workspace_resource_id):
        from promptflow import PFClient

        client = PFClient(config={"connection.provider": remote_workspace_resource_id})
        output = client.test(flow=flow_test_dir / "web_classification")
        assert output.keys() == {"category", "evidence"}

    @pytest.mark.usefixtures("mock_get_user_identity_info")
    def test_list_flows(self, pf):
        flows = pf.flows.list(max_results=3)
        for flow in flows:
            print(json.dumps(flow._to_dict(), indent=4))
        assert len(flows) == 3

    def test_list_flows_invalid_cases(self, pf):
        with pytest.raises(FlowOperationError, match="'max_results' must be a positive integer"):
            pf.flows.list(max_results=0)

        with pytest.raises(FlowOperationError, match="'flow_type' must be one of"):
            pf.flows.list(flow_type="unknown")

        with pytest.raises(FlowOperationError, match="Invalid list view type"):
            pf.flows.list(list_view_type="invalid")
