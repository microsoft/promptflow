# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow._sdk._errors import FlowOperationError

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.mark.unittest
class TestFlow:
    def test_create_flow_with_invalid_parameters(self, remote_client):
        with pytest.raises(ValueError, match=r"Flow file .*? does not exist."):
            remote_client.flows.create_or_update(source="fake_source")

        flow_source = flow_test_dir / "web_classification/"
        with pytest.raises(FlowOperationError, match="Flow name must be a string"):
            remote_client.flows.create_or_update(source=flow_source, flow_name=object())

        with pytest.raises(FlowOperationError, match="Flow type 'fake_flow_type' is not supported"):
            remote_client.flows.create_or_update(source=flow_source, flow_type="fake_flow_type")

        with pytest.raises(FlowOperationError, match="Description must be a string"):
            remote_client.flows.create_or_update(source=flow_source, description=object())

        with pytest.raises(FlowOperationError, match="got non-dict or non-string key/value in tags"):
            remote_client.flows.create_or_update(source=flow_source, tags={"key": object()})

    def test_create_flow_when_flow_name_already_exist(self, remote_client, mocker: MockerFixture):
        mocker.patch(
            "promptflow.azure.operations._flow_operations.FlowFileStorageClient._check_file_share_directory_exist",
            return_value=True,
        )
        flow_source = flow_test_dir / "web_classification/"
        with pytest.raises(FlowOperationError, match="Please change the flow folder name"):
            remote_client.flows.create_or_update(source=flow_source)

    def test_parse_flow_portal_url(self, remote_client):
        flow_resource_id = (
            "azureml://locations/eastus/workspaces/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/flows/"
            "1176ba41-d529-4cc4-9629-4ee3f474c5e2"
        )
        url = remote_client.flows._get_flow_portal_url(flow_resource_id)
        expected_portal_url = (
            f"https://ml.azure.com/prompts/flow/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/"
            f"1176ba41-d529-4cc4-9629-4ee3f474c5e2/details?wsid={remote_client.flows._common_azure_url_pattern}"
        )
        assert url == expected_portal_url
