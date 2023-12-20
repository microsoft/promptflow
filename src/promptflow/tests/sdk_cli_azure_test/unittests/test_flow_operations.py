# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._sdk._errors import FlowOperationError
from promptflow.exceptions import UserErrorException

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.mark.unittest
class TestFlowOperations:
    def test_create_flow_with_invalid_parameters(self, pf):
        with pytest.raises(UserErrorException, match=r"Flow source must be a directory with"):
            pf.flows.create_or_update(flow="fake_source")

        flow_source = flow_test_dir / "web_classification/"
        with pytest.raises(UserErrorException, match="Not a valid string"):
            pf.flows.create_or_update(flow=flow_source, display_name=object())

        with pytest.raises(UserErrorException, match="Must be one of: standard, evaluation, chat"):
            pf.flows.create_or_update(flow=flow_source, type="unknown")

        with pytest.raises(UserErrorException, match="Not a valid string"):
            pf.flows.create_or_update(flow=flow_source, description=object())

        with pytest.raises(UserErrorException, match="Not a valid string"):
            pf.flows.create_or_update(flow=flow_source, tags={"key": object()})

        with pytest.raises(UserErrorException, match="Unknown field"):
            pf.flows.create_or_update(flow=flow_source, random="random")

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

    def test_list_flows_invalid_cases(self, pf):
        with pytest.raises(FlowOperationError, match="'max_results' must be a positive integer"):
            pf.flows.list(max_results=0)

        with pytest.raises(FlowOperationError, match="'flow_type' must be one of"):
            pf.flows.list(flow_type="unknown")

        with pytest.raises(FlowOperationError, match="Invalid list view type"):
            pf.flows.list(list_view_type="invalid")
