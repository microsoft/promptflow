import pytest
import json

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
        )
        assert "10" == result

    def test_openai_gpt4v_stream_chat(self, openai_provider, example_prompt_template_with_image, example_image):
        result = openai_provider.chat(
            prompt=example_prompt_template_with_image,
            model="gpt-4-vision-preview",
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
