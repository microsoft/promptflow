# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import uuid
from pathlib import Path

import pytest

from promptflow._cli._pf_azure._flow import list_flows
from promptflow._sdk._constants import FlowType

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


# TODO: enable the following tests after test CI can access test workspace
@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
class TestFlow:
    def test_create_flow(self, remote_client, capfd):
        flow_source = flow_test_dir / "web_classification/"
        flow_name = f"{flow_source.name}_{uuid.uuid4()}"
        remote_client.flows.create_or_update(
            source=flow_source, flow_name=flow_name, flow_type=FlowType.STANDARD, tags={"owner": "hod"}
        )
        out, err = capfd.readouterr()
        assert "Flow created successfully" in out

    @pytest.mark.skip(reason="This test is not ready yet.")
    def test_list_flows(self, client):
        flows = list_flows(
            subscription_id=client.subscription_id,
            resource_group=client.resource_group_name,
            workspace_name=client.workspace_name,
        )
        print(flows)
