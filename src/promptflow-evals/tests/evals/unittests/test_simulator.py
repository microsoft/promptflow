# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401
# flake8: noqa: F841


import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from promptflow.evals.synthetic import Simulator


@pytest.fixture()
def async_callback():
    async def callback(x):
        return x

    yield callback


@pytest.mark.unittest
class TestSimulator(unittest.TestCase):
    def test_simulator_init_returns_callable(self):
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
        }
        simulator = Simulator(azure_ai_project=azure_ai_project)
        assert callable(simulator)

    def test_simulator_throws_exception(self):
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
        }
        simulator = Simulator(azure_ai_project=azure_ai_project)
        assert callable(simulator)
        outputs = None
        with self.assertRaises(Exception):
            outputs = asyncio.run(
                simulator(
                    target=async_callback,
                    text="text",
                    num_queries=1,
                    max_conversation_turns=2,
                    user_persona=[
                        f"I am a student and I want to learn more about the text",
                    ],
                )
            )
        assert outputs is None
