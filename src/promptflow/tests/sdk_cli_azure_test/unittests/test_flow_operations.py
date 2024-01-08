# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from pathlib import Path

import pytest

from promptflow._sdk._errors import FlowOperationError
from promptflow._utils.logger_utils import get_cli_sdk_logger
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

    def test_create_flow_with_warnings(self, pf, caplog):
        flow_source = flow_test_dir / "web_classification/"
        logger = get_cli_sdk_logger()
        logger.propagate = True  # enable caplog to see the log
        with caplog.at_level(logging.WARNING):
            pf.flows._validate_flow_creation_parameters(source=flow_source, random="random")
            assert "random: Unknown field" in caplog.text

    def test_list_flows_invalid_cases(self, pf):
        with pytest.raises(FlowOperationError, match="'max_results' must be a positive integer"):
            pf.flows.list(max_results=0)

        with pytest.raises(FlowOperationError, match="'flow_type' must be one of"):
            pf.flows.list(flow_type="unknown")

        with pytest.raises(FlowOperationError, match="Invalid list view type"):
            pf.flows.list(list_view_type="invalid")
