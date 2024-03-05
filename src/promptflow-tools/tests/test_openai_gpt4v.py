import pytest
from unittest.mock import patch

from promptflow.tools.openai_gpt4v import OpenAI


@pytest.fixture
def openai_provider(open_ai_connection) -> OpenAI:
    return OpenAI(open_ai_connection)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip_if_no_api_key("open_ai_connection")
class TestOpenAIGPT4V:
    def test_openai_gpt4v_chat(self, openai_provider, example_prompt_template_with_image, example_image):
        result = openai_provider.chat(
            prompt=example_prompt_template_with_image,
            model="gpt-4-vision-preview",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
            seed=123
        )
        assert "10" == result
        # verify if openai built-in retry mechanism is disabled
        assert openai_provider._client.max_retries == 0

    def test_openai_gpt4v_stream_chat(self, openai_provider, example_prompt_template_with_image, example_image):
        result = openai_provider.chat(
            prompt=example_prompt_template_with_image,
            model="gpt-4-vision-preview",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
            stream=True,
        )
        answer = ""
        while True:
            try:
                answer += next(result)
            except Exception:
                break
        assert "10" == answer

    def test_correctly_pass_params(self, openai_provider, example_prompt_template_with_image, example_image):
        seed_value = 123
        with patch.object(openai_provider._client.chat.completions, 'create') as mock_create:
            openai_provider.chat(
                prompt=example_prompt_template_with_image,
                deployment_name="gpt-4v",
                max_tokens=480,
                temperature=0,
                question="which number did you see in this picture?",
                image_input=example_image,
                seed=seed_value
            )
            mock_create.assert_called_once()
            called_with_params = mock_create.call_args[1]
            assert called_with_params['seed'] == seed_value
