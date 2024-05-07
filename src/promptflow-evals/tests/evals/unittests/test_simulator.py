# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401
# flake8: noqa: F841

import asyncio
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
    @patch("promptflow.evals.synthetic._model_tools._rai_client.RAIClient._get_service_discovery_url")
    def test_initialization_with_all_valid_scenarios(self, mock_get_service_discovery_url):
        mock_get_service_discovery_url.return_value = "some-url"
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
            "credential": "test_credential",
        }
        available_scenarios = [
            "adv_conversation",
            "adv_qa",
            "adv_summarization",
            "adv_search",
            "adv_rewrite",
            "adv_content_gen_ungrounded",
            "adv_content_gen_grounded",
        ]
        for scenario in available_scenarios:
            simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)
            assert mock_get_service_discovery_url.called
            assert callable(simulator)

    @patch("promptflow.evals.synthetic._model_tools._rai_client.RAIClient._get_service_discovery_url")
    @patch("promptflow.evals.synthetic._model_tools.AdversarialTemplateHandler._get_content_harm_template_collections")
    def test_simulator_raises_validation_error_with_unsupported_scenario(
        self, _get_content_harm_template_collections, _get_service_discovery_url
    ):
        _get_content_harm_template_collections.return_value = []
        _get_service_discovery_url.return_value = "some-url"
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
            "credential": "test_credential",
        }

        async def callback(x):
            return x

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)
        with pytest.raises(ValueError):
            outputs = asyncio.run(
                simulator(
                    scenario="unknown-scenario", max_conversation_turns=1, max_simulation_results=3, target=callback
                )
            )
