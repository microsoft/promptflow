# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401
# flake8: noqa: F841

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator


@pytest.fixture()
def async_callback():
    async def callback(x):
        return x

    yield callback


@pytest.mark.unittest
class TestSimulator:
    @patch("promptflow.evals.synthetic._model_tools._rai_client.RAIClient._get_service_discovery_url")
    @patch("promptflow.evals.synthetic._model_tools.AdversarialTemplateHandler._get_content_harm_template_collections")
    @patch("promptflow.evals.synthetic.adversarial_simulator.AdversarialSimulator._simulate_async")
    @patch("promptflow.evals.synthetic.adversarial_simulator.AdversarialSimulator._ensure_service_dependencies")
    def test_initialization_with_all_valid_scenarios(
        self,
        mock_ensure_service_dependencies,
        mock_get_content_harm_template_collections,
        mock_simulate_async,
        mock_get_service_discovery_url,
    ):
        mock_get_service_discovery_url.return_value = "http://some.url/discovery/"
        mock_simulate_async.return_value = MagicMock()
        mock_get_content_harm_template_collections.return_value = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        mock_ensure_service_dependencies.return_value = True
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
            "credential": "test_credential",
        }
        available_scenarios = [
            AdversarialScenario.ADVERSARIAL_CONVERSATION,
            AdversarialScenario.ADVERSARIAL_QA,
            AdversarialScenario.ADVERSARIAL_SUMMARIZATION,
            AdversarialScenario.ADVERSARIAL_SEARCH,
            AdversarialScenario.ADVERSARIAL_REWRITE,
            AdversarialScenario.ADVERSARIAL_CONTENT_GEN_UNGROUNDED,
            AdversarialScenario.ADVERSARIAL_CONTENT_GEN_GROUNDED,
        ]
        for scenario in available_scenarios:
            simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)
            assert callable(simulator)
            simulator(scenario=scenario, max_conversation_turns=1, max_simulation_results=3, target=async_callback)

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

    @patch("promptflow.evals.synthetic._model_tools._rai_client.RAIClient._get_service_discovery_url")
    @patch("promptflow.evals.synthetic._model_tools.AdversarialTemplateHandler._get_content_harm_template_collections")
    @patch("promptflow.evals.synthetic.adversarial_simulator.AdversarialSimulator._simulate_async")
    @patch("promptflow.evals.synthetic.adversarial_simulator.AdversarialSimulator._ensure_service_dependencies")
    def test_initialization_parity_with_evals(
        self,
        mock_ensure_service_dependencies,
        mock_get_content_harm_template_collections,
        mock_simulate_async,
        mock_get_service_discovery_url,
    ):
        mock_get_service_discovery_url.return_value = "http://some.url/discovery/"
        mock_simulate_async.return_value = MagicMock()
        mock_get_content_harm_template_collections.return_value = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        mock_ensure_service_dependencies.return_value = True
        azure_ai_project = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "project_name": "test_workspace",
        }
        available_scenarios = [
            AdversarialScenario.ADVERSARIAL_CONVERSATION,
            AdversarialScenario.ADVERSARIAL_QA,
            AdversarialScenario.ADVERSARIAL_SUMMARIZATION,
            AdversarialScenario.ADVERSARIAL_SEARCH,
            AdversarialScenario.ADVERSARIAL_REWRITE,
            AdversarialScenario.ADVERSARIAL_CONTENT_GEN_UNGROUNDED,
            AdversarialScenario.ADVERSARIAL_CONTENT_GEN_GROUNDED,
        ]
        for scenario in available_scenarios:
            simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential="test_credential")
            assert callable(simulator)
            simulator(scenario=scenario, max_conversation_turns=1, max_simulation_results=3, target=async_callback)
