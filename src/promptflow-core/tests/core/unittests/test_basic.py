# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._utils.user_agent_utils import append_promptflow_package_ua
from promptflow.tracing._operation_context import OperationContext


@pytest.mark.unittest
class TestBasic:
    def test_import(self):
        assert True

    def test_package_ua(self):
        opc = OperationContext()
        append_promptflow_package_ua(opc)
        assert "promptflow-core" in opc.user_agent
