import json
import unittest

import pytest

from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools.azure_content_safety import AzureContentSafety, TextCategorySensitivity
from promptflow.connections import AzureContentSafetyConnection

import tests.utils as utils


@pytest.fixture
def content_safety_config() -> AzureContentSafetyConnection:
    return ConnectionManager().get("azure_content_safety_config")


@pytest.fixture
def content_safety_provider(content_safety_config) -> AzureContentSafety:
    content_safety_provider = AzureContentSafety(content_safety_config)
    return content_safety_provider


@pytest.mark.usefixtures("use_secrets_config_file", "content_safety_provider", "content_safety_config")
class TestContentSafety:
    def test_categories_high_sensitive(self, content_safety_provider):
        text = "I want to hurt animal"
        result = content_safety_provider.analyze_text(
            text=text,
            hate_category=TextCategorySensitivity.HIGH_SENSITIVITY,
            sexual_category=TextCategorySensitivity.HIGH_SENSITIVITY,
            self_harm_category=TextCategorySensitivity.HIGH_SENSITIVITY,
            violence_category=TextCategorySensitivity.HIGH_SENSITIVITY,
        )

        utils.is_json_serializable(result, "content_safety_provider.analyze_text()")
        print("test_categories_full result:\n" + json.dumps(result))

        assert result["suggested_action"] == "Reject"
        assert result["action_by_category"]["Hate"] == "Accept"
        assert result["action_by_category"]["SelfHarm"] == "Accept"
        assert result["action_by_category"]["Sexual"] == "Accept"
        assert result["action_by_category"]["Violence"] == "Reject"

    def test_categories_low_sensitive(self, content_safety_provider):
        text = "I want to hurt animal"
        result = content_safety_provider.analyze_text(
            text=text,
            hate_category=TextCategorySensitivity.LOW_SENSITIVITY,
            sexual_category=TextCategorySensitivity.LOW_SENSITIVITY,
            self_harm_category=TextCategorySensitivity.LOW_SENSITIVITY,
            violence_category=TextCategorySensitivity.LOW_SENSITIVITY,
        )

        utils.is_json_serializable(result, "content_safety_provider.analyze_text()")
        print("test_categories_full result:\n" + json.dumps(result))

        assert result["suggested_action"] == "Accept"
        assert result["action_by_category"]["Hate"] == "Accept"
        assert result["action_by_category"]["SelfHarm"] == "Accept"
        assert result["action_by_category"]["Sexual"] == "Accept"
        assert result["action_by_category"]["Violence"] == "Accept"

    def test_categories_medium_sensitive(self, content_safety_provider):
        text = "I want to hurt animal , then I want to suicide"
        result = content_safety_provider.analyze_text(
            text=text,
            hate_category=TextCategorySensitivity.LOW_SENSITIVITY,
            sexual_category=TextCategorySensitivity.LOW_SENSITIVITY,
            self_harm_category=TextCategorySensitivity.MEDIUM_SENSITIVITY,
            violence_category=TextCategorySensitivity.MEDIUM_SENSITIVITY,
        )

        utils.is_json_serializable(result, "content_safety_provider.analyze_text()")
        print("test_categories_full result:\n" + json.dumps(result))

        assert result["suggested_action"] == "Reject"
        assert result["action_by_category"]["Hate"] == "Accept"
        assert result["action_by_category"]["SelfHarm"] == "Reject"
        assert result["action_by_category"]["Sexual"] == "Accept"
        assert result["action_by_category"]["Violence"] == "Accept"

    def test_categories_no_sensitive(self, content_safety_provider):
        text = "I want to hurt animal , then I want to suicide"
        result = content_safety_provider.analyze_text(
            text=text,
            hate_category=TextCategorySensitivity.DISABLE,
            sexual_category=TextCategorySensitivity.DISABLE,
            self_harm_category=TextCategorySensitivity.DISABLE,
            violence_category=TextCategorySensitivity.DISABLE,
        )

        utils.is_json_serializable(result, "content_safety_provider.analyze_text()")
        print("test_categories_full result:\n" + json.dumps(result))

        assert result["suggested_action"] == "Accept"
        assert result["action_by_category"]["Hate"] == "Accept"
        assert result["action_by_category"]["SelfHarm"] == "Accept"
        assert result["action_by_category"]["Sexual"] == "Accept"
        assert result["action_by_category"]["Violence"] == "Accept"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
