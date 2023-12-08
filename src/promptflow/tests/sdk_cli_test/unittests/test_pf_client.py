# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pytest

from promptflow import PFClient
from promptflow._sdk._utils import get_client_user_agent


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    def test_pf_client_user_agent(self):
        PFClient()
        assert "promptflow-sdk" in get_client_user_agent()
        assert "promptflow/" not in get_client_user_agent()
