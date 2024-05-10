# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json

import pytest
from sdk_cli_azure_test.conftest import FLOWS_DIR

from promptflow._sdk._constants import FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow.azure._entities._flow import Flow
from promptflow.exceptions import UserErrorException

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
)
@pytest.mark.xdist_group(name="pfazure_flow")
class TestFlow:
    def test_create_flow(self, created_flow: Flow):
        # most of the assertions are in the fixture itself
        assert isinstance(created_flow, Flow)
        flow_tools_json_path = FLOWS_DIR / "simple_hello_world" / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        assert not flow_tools_json_path.exists()

    def test_get_flow(self, pf, created_flow: Flow):
        result = pf.flows.get(name=created_flow.name)

        # assert created flow is the same as the one retrieved
        attributes = vars(result)
        for attr in attributes:
            assert getattr(result, attr) == getattr(created_flow, attr), f"Assertion failed for attribute: {attr!r}"

    def test_update_flow(self, pf, created_flow: Flow):

        test_meta = {
            "display_name": "SDK test flow",
            "description": "SDK test flow description",
            "tags": {"owner": "sdk-test", "key1": "value1"},
        }
        # update flow
        updated_flow = pf.flows.create_or_update(flow=created_flow, **test_meta)

        assert updated_flow.display_name == test_meta["display_name"]
        assert updated_flow.description == test_meta["description"]
        assert updated_flow.tags == test_meta["tags"]

        # test update with wrong flow id
        with pytest.raises(UserErrorException, match=r"Flow with id fake_flow_name not found"):
            updated_flow.name = "fake_flow_name"
            pf.flows.create_or_update(updated_flow, display_name="A new test flow")

    @pytest.mark.skipif(
        condition=not pytest.is_live,
        reason="Complicated test combining `pf flow test` and global config",
    )
    def test_flow_test_with_config(self, remote_workspace_resource_id):
        from promptflow import PFClient

        client = PFClient(config={"connection.provider": remote_workspace_resource_id})
        output = client.test(flow=FLOWS_DIR / "web_classification")
        assert output.keys() == {"category", "evidence"}

    @pytest.mark.usefixtures("mock_get_user_identity_info")
    def test_list_flows(self, pf):
        flows = pf.flows.list(max_results=3)
        for flow in flows:
            print(json.dumps(flow._to_dict(), indent=4))
        assert len(flows) == 3
