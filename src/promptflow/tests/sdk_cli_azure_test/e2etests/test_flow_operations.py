# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from pathlib import Path

import pytest

from promptflow.azure._entities._flow import Flow

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD
from ..recording_utilities import is_live

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
    def test_create_flow(self, created_flow: Flow):
        # most of the assertions are in the fixture itself
        assert isinstance(created_flow, Flow)

    def test_get_flow(self, pf, created_flow: Flow):
        result = pf.flows.get(name=created_flow.name)

        # assert created flow is the same as the one retrieved
        attributes = vars(result)
        for attr in attributes:
            assert getattr(result, attr) == getattr(created_flow, attr), f"Assertion failed for attribute: {attr!r}"

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
