import pytest
from unittest.mock import patch

from promptflow.tools.aoai_gpt4v import list_deployment_names
from tests.utils import Deployment
from promptflow.tools.llm_vision import llm_vision


@pytest.mark.usefixtures("use_secrets_config_file")
class TestLLMVision:
    def test_aoai_gpt4v_chat(self, azure_open_ai_connection, example_prompt_template_with_image, example_image):
        result = llm_vision(
            connection=azure_open_ai_connection,
            api="chat",
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
            seed=123
        )

        assert "10" == result

    def test_aoai_gpt4v_stream_chat(self, azure_open_ai_connection, example_prompt_template_with_image, example_image):
        result = llm_vision(
            connection=azure_open_ai_connection,
            api="chat",
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
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

    def test_correctly_pass_params(self, aoai_vision_provider, example_prompt_template_with_image, example_image):
        seed_value = 123
        with patch("openai.resources.chat.Completions.create") as mock_create:
            aoai_vision_provider.chat(
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
