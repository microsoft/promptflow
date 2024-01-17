# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from unittest.mock import MagicMock, patch

import pytest

from promptflow.exceptions import UserErrorException


@pytest.mark.unittest
class TestUtils:
    def test_url_parse(self):
        from promptflow.azure._utils._url_utils import BulkRunId, BulkRunURL

        flow_id = (
            "azureml://experiment/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/flow/"
            "0ab9d2dd-3bac-4b68-bb28-12af959b1165/bulktest/715efeaf-b0b4-4778-b94a-2538152b8766/"
            "run/f88faee6-e510-45b7-9e63-08671b30b3a2"
        )
        flow_id = BulkRunId(flow_id)
        assert flow_id.experiment_id == "3e123da1-f9a5-4c91-9234-8d9ffbb39ff5"
        assert flow_id.flow_id == "0ab9d2dd-3bac-4b68-bb28-12af959b1165"
        assert flow_id.bulk_test_id == "715efeaf-b0b4-4778-b94a-2538152b8766"

        flow_run_url = (
            "https://ml.azure.com/prompts/flow/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/"
            "0ab9d2dd-3bac-4b68-bb28-12af959b1165/bulktest/715efeaf-b0b4-4778-b94a-2538152b8766/"
            "details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow/"
            "providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus"
        )
        flow_url = BulkRunURL(flow_run_url)
        assert flow_url.experiment_id == "3e123da1-f9a5-4c91-9234-8d9ffbb39ff5"
        assert flow_url.flow_id == "0ab9d2dd-3bac-4b68-bb28-12af959b1165"
        assert flow_url.bulk_test_id == "715efeaf-b0b4-4778-b94a-2538152b8766"

    def test_forbidden_new_caller(self):
        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller

        with pytest.raises(UserErrorException) as e:
            FlowServiceCaller(MagicMock(), MagicMock(), MagicMock())
        assert "_FlowServiceCallerFactory" in str(e.value)

    def test_get_user_identity_info(self):
        import jwt

        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller

        mock_oid, mock_tid = "mock_oid", "mock_tid"

        def mock_init(*args, **kwargs) -> str:
            self = args[0]
            self._credential = None

        def mock_get_arm_token(*args, **kwargs) -> str:
            return jwt.encode(
                payload={
                    "oid": mock_oid,
                    "tid": mock_tid,
                },
                key="",
            )

        with patch(
            "promptflow.azure._restclient.flow_service_caller.get_arm_token",
            new=mock_get_arm_token,
        ):
            with patch.object(FlowServiceCaller, "__init__", new=mock_init):
                service_caller = FlowServiceCaller(workspace=None, credential=None, operation_scope=None)
                user_object_id, user_tenant_id = service_caller._get_user_identity_info()
                assert user_object_id == mock_oid
                assert user_tenant_id == mock_tid
