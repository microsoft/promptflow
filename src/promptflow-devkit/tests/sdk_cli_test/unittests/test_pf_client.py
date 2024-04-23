# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.client import PFClient


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    def test_pf_client_user_agent(self):
        PFClient()
        assert "promptflow-sdk" in ClientUserAgentUtil.get_user_agent()
        # TODO: Add back assert and run this test case separatly to avoid concurrent issue.
        # assert "promptflow/" not in ClientUserAgentUtil.get_user_agent()
