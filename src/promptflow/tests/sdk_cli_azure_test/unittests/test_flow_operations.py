# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._sdk._errors import FlowOperationError

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.mark.unittest
class TestFlowOperations:
    def test_create_flow_with_invalid_parameters(self, pf):
        with pytest.raises(ValueError, match=r"Flow file .*? does not exist."):
            pf.flows.create_or_update(flow="fake_source")

        flow_source = flow_test_dir / "web_classification/"
        with pytest.raises(FlowOperationError, match="Flow name must be a string"):
            pf.flows.create_or_update(flow=flow_source, display_name=object())

        with pytest.raises(FlowOperationError, match="Flow type 'fake_flow_type' is not supported"):
            pf.flows.create_or_update(flow=flow_source, type="fake_flow_type")

        with pytest.raises(FlowOperationError, match="Description must be a string"):
            pf.flows.create_or_update(flow=flow_source, description=object())

        with pytest.raises(FlowOperationError, match="got non-dict or non-string key/value in tags"):
            pf.flows.create_or_update(flow=flow_source, tags={"key": object()})

    def test_parse_flow_portal_url(self, pf):
        experiment_id = "3e123da1-f9a5-4c91-9234-8d9ffbb39ff5"
        flow_id = "1176ba41-d529-4cc4-9629-4ee3f474c5e2"
        flow_resource_id = f"azureml://locations/eastus/workspaces/{experiment_id}/flows/{flow_id}"

        # workspace is aml studio
        with patch.object(pf.flows._workspace, "_kind", "default"):
            url = pf.flows._get_flow_portal_url_from_resource_id(flow_resource_id)
            expected_portal_url = (
                f"https://ml.azure.com/prompts/flow/{experiment_id}/"
                f"{flow_id}/details?wsid={pf._service_caller._common_azure_url_pattern}"
            )
            assert url == expected_portal_url

        # workspace is azure ai studio
        with patch.object(pf.flows._workspace, "_kind", "project"):
            url = pf.flows._get_flow_portal_url_from_resource_id(flow_resource_id)
            expected_portal_url = (
                f"https://ai.azure.com/projectflows/{flow_id}/"
                f"{experiment_id}/details/Flow?wsid={pf._service_caller._common_azure_url_pattern}"
            )
            assert url == expected_portal_url
