import pytest

from promptflow.tools.azure_content_safety import analyze_text


@pytest.mark.skip("Skipping - Key based authentication is disabled for this resource")
@pytest.mark.usefixtures("use_secrets_config_file")
class TestAzureContentSafety:
    def test_azure_content_safety_analyze_happy_path(self, azure_content_safety_connection):
        text = "I hate you."
        result = analyze_text(
            connection=azure_content_safety_connection,
            text=text
        )
        assert "suggested_action" in result
        assert "action_by_category" in result
