# import pytest
#
# from promptflow.tools.azure_content_safety import analyze_text
#
#
# @pytest.mark.usefixtures("use_secrets_config_file")
# @pytest.mark.skip_if_no_api_key("azure_content_safety_connection")
# class TestAzureContentSafety:
#     def test_azure_content_safety_connection(self, azure_content_safety_connection):
#         result = analyze_text(
#             connection=azure_content_safety_connection,
#             text="The food was delicious and the waiter"
#         )
#         assert result is not None
