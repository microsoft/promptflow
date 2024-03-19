import pytest
from unittest.mock import patch

from promptflow.tools.aoai_gpt4v import list_deployment_names
from tests.utils import Deployment


@pytest.mark.usefixtures("use_secrets_config_file")
class TestAzureOpenAIGPT4V:
    def test_openai_gpt4v_chat(self, aoai_vision_provider, example_prompt_template_with_image, example_image):
        result = aoai_vision_provider.chat(
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
            seed=123
        )
        assert "10" == result
        # verify if openai built-in retry mechanism is disabled
        assert aoai_vision_provider._client.max_retries == 0

    def test_openai_gpt4v_stream_chat(self, aoai_vision_provider, example_prompt_template_with_image, example_image):
        result = aoai_vision_provider.chat(
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
        with patch.object(aoai_vision_provider._client.chat.completions, 'create') as mock_create:
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

    def test_list_deployment_names(self):
        with patch('promptflow.tools.aoai_gpt4v.list_deployment_connections') as mock_list:
            mock_list.return_value = {
                Deployment("deployment1", "model1", "vision-preview"),
                Deployment("deployment2", "model2", "version2")
            }

            res = list_deployment_names("sub", "rg", "ws", "con")
            assert len(res) == 1
            assert res[0].get("value") == "deployment1"
            assert res[0].get("display_value") == "deployment1"
