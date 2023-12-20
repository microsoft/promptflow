import pytest

from promptflow.tools.azure_content_safety import analyze_text
@pytest.mark.usefixtures("use_secrets_config_file")
class TestAzureContentSafety:
    def test_azure_content_safety_analyze(self, azure_content_safety_connection):
        result = analyze_text(
            connection=azure_content_safety_connection,
            text="This is test input",
        )