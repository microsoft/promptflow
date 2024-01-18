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
            pf.flows.create_or_update(flow=flow_source, display_name=False)

        with pytest.raises(UserErrorException, match="Must be one of: standard, evaluation, chat"):
            pf.flows.create_or_update(flow=flow_source, type="unknown")

        with pytest.raises(UserErrorException, match="Not a valid string"):
            pf.flows.create_or_update(flow=flow_source, description=False)

        with pytest.raises(UserErrorException, match="Not a valid string"):
            pf.flows.create_or_update(flow=flow_source, tags={"key": False})

    @pytest.mark.usefixtures("enable_logger_propagate")
    def test_create_flow_with_warnings(self, pf, caplog):
        flow_source = flow_test_dir / "web_classification/"
        pf.flows._validate_flow_creation_parameters(source=flow_source, random="random")
        assert "random: Unknown field" in caplog.text

    def test_list_flows_invalid_cases(self, pf):
        with pytest.raises(FlowOperationError, match="'max_results' must be a positive integer"):
            pf.flows.list(max_results=0)

        with pytest.raises(FlowOperationError, match="'flow_type' must be one of"):
            pf.flows.list(flow_type="unknown")

        with pytest.raises(FlowOperationError, match="Invalid list view type"):
            pf.flows.list(list_view_type="invalid")

    def test_get_user_identity_info(self):
        # we have a fixture "mock_get_user_identity_info" to mock this function during record and replay
        # as we don't want to deal with token in these modes; meanwhile, considering coverage, add this
        # unit test to try to cover this code path.
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
