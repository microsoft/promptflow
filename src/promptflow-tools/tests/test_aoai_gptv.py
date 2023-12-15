import pytest

from promptflow.tools.aoai_gpt4v import AzureOpenAI


@pytest.fixture
def azure_openai_provider(azure_open_ai_connection) -> AzureOpenAI:
    return AzureOpenAI(azure_open_ai_connection)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip_if_no_api_key("azure_open_ai_connection")
@pytest.mark.skip("Skipping until we have a Azure OpenAI GPT-4 Vision deployment")
class TestAzureOpenAIGPT4V:
    def test_openai_gpt4v_chat(self, azure_openai_provider, example_prompt_template_with_image, example_image):
        result = azure_openai_provider.chat(
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
        )
        assert "10" == result

    def test_openai_gpt4v_stream_chat(self, azure_openai_provider, example_prompt_template_with_image, example_image):
        result = azure_openai_provider.chat(
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
        )
        answer = ""
        while True:
            try:
                answer += next(result)
            except Exception:
                break
        assert "10" == result
