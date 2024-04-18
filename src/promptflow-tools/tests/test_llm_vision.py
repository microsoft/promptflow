from unittest.mock import patch

import pytest
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.tools.llm_vision import llm_vision


@pytest.mark.usefixtures("use_secrets_config_file")
class TestLLMVision:
    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name",
        [
            pytest.param("azure_open_ai_connection", "gpt-4v"),
            pytest.param("open_ai_connection", "gpt-4-vision-preview",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_vision_chat(self, request, connection_type, model_or_deployment_name,
                             example_prompt_template_with_image, example_image):
        connection = request.getfixturevalue(connection_type)
        result = llm_vision(
            connection=connection,
            api="chat",
            prompt=example_prompt_template_with_image,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
            seed=123
        )

        assert "10" == result

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name",
        [
            pytest.param("azure_open_ai_connection", "gpt-4v"),
            pytest.param("open_ai_connection", "gpt-4-vision-preview",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_aoai_gpt4v_stream_chat(self, request, connection_type, model_or_deployment_name,
                                    example_prompt_template_with_image, example_image):
        connection = request.getfixturevalue(connection_type)
        result = llm_vision(
            connection=connection,
            api="chat",
            prompt=example_prompt_template_with_image,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
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

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name",
        [
            pytest.param("azure_open_ai_connection", "gpt-4v"),
            pytest.param("open_ai_connection", "gpt-4-vision-preview",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_correctly_pass_params(self, request, connection_type, model_or_deployment_name,
                                   example_prompt_template_with_image, example_image):
        seed_value = 123
        with patch("openai.resources.chat.Completions.create") as mock_create:
            connection = request.getfixturevalue(connection_type)
            llm_vision(
                connection=connection,
                api="chat",
                prompt=example_prompt_template_with_image,
                deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
                model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
                max_tokens=480,
                temperature=0,
                question="which number did you see in this picture?",
                image_input=example_image,
                seed=seed_value
            )
            mock_create.assert_called_once()
            called_with_params = mock_create.call_args[1]
            assert called_with_params['seed'] == seed_value

    # the test is to verify the tool can support serving streaming functionality.
    def test_streaming_option_parameter_is_set(self):
        assert getattr(llm_vision, "_streaming_option_parameter") == "stream"
