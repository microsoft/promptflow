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
    @patch("promptflow.evals.synthetic._model_tools._rai_client.RAIClient._get_service_discovery_url")
    def test_initialization_with_all_valid_templates(self, mock_get_service_discovery_url):
        mock_get_service_discovery_url.return_value = "some-url"
        project_scope = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "workspace_name": "test_workspace",
            "credential": "test_credential",
        }
        available_templates = [
            "adv_conversation",
            "adv_qa",
            "adv_summarization",
            "adv_search",
            "adv_rewrite",
            "adv_content_gen_ungrounded",
            "adv_content_gen_grounded",
        ]
        for template in available_templates:
            simulator = AdversarialSimulator(template=template, project_scope=project_scope)
            assert mock_get_service_discovery_url.called
            assert callable(simulator)

    def test_simulator_raises_validation_error_with_unsupported_template(self):
        project_scope = {
            "subscription_id": "test_subscription",
            "resource_group_name": "test_resource_group",
            "workspace_name": "test_workspace",
            "credential": "test_credential",
        }
        with pytest.raises(ValueError):
            AdversarialSimulator(template="unsupported_template", project_scope=project_scope)
