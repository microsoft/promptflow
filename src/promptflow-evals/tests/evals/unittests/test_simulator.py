# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401
# flake8: noqa: F841

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from promptflow.evals.synthetic import AdversarialSimulator


@pytest.fixture()
def async_callback():
    async def callback(x):
        return x

    yield callback


@pytest.mark.unittest
class TestSimulator:
    def test_initialization(self):
        # Setup
        template = "adv_conversation"
        project_scope = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "workspace_name": "test_workspace",
            "credential": "credentials",
        }

        # Exercise
        simulator = AdversarialSimulator(template=template, project_scope=project_scope)

        # Verify
        # check if simulator is callable
        assert callable(simulator)
