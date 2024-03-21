# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from promptflow import PFClient
from promptflow._utils.user_agent_utils import ClientUserAgentUtil


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    def test_pf_client_user_agent(self):
        PFClient()
        assert "promptflow-sdk" in ClientUserAgentUtil.get_user_agent()
        assert "promptflow/" not in ClientUserAgentUtil.get_user_agent()
