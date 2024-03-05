import pytest
import json
from unittest.mock import patch

from promptflow.tools.openai import chat, completion, OpenAI
from promptflow.tools.exception import WrappedOpenAIError


@pytest.fixture
def openai_provider(open_ai_connection) -> OpenAI:
    return OpenAI(open_ai_connection)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip_if_no_api_key("open_ai_connection")
class TestOpenAI:
    def test_openai_completion(self, openai_provider):
        prompt_template = "please complete this sentence: world war II "
        openai_provider.completion(prompt=prompt_template)

    def test_openai_stream_completion(self, openai_provider):
        prompt_template = "please complete this sentence: world war II "
        openai_provider.completion(prompt=prompt_template, stream=True)

    def test_openai_completion_api(self, open_ai_connection):
        prompt_template = "please complete this sentence: world war II "
        completion(open_ai_connection, prompt=prompt_template)

    def test_openai_chat(self, openai_provider, example_prompt_template, chat_history):
        result = openai_provider.chat(
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            max_tokens=32,
            temperature=0,
            user_input="Fill in more details about trend 2.",
            chat_history=chat_history,
            seed=42
        )
        assert "trend 2" in result.lower()
        # verify if openai built-in retry mechanism is disabled
        assert openai_provider._client.max_retries == 0

    def test_openai_stream_chat(self, openai_provider, example_prompt_template, chat_history):
        result = openai_provider.chat(
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            max_tokens=32,
            temperature=0,
            user_input="Fill in more details about trend 2.",
            chat_history=chat_history,
            stream=True,
        )
        answer = ""
        while True:
            try:
                answer += next(result)
            except Exception:
                break
        assert "trend 2" in answer.lower()

    def test_openai_chat_api(self, open_ai_connection, example_prompt_template, chat_history):
        result = chat(
            connection=open_ai_connection,
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            max_tokens="inF",
            temperature=0,
            user_input="Write a slogan for product X",
            chat_history=chat_history,
        )
        assert "Product X".lower() in result.lower()

    def test_correctly_pass_params(self, openai_provider, example_prompt_template, chat_history):
        seed_value = 123
        with patch.object(openai_provider._client.chat.completions, 'create') as mock_create:
            openai_provider.chat(
                prompt=example_prompt_template,
                deployment_name="gpt-35-turbo",
                max_tokens="32",
                temperature=0,
                user_input="Fill in more details about trend 2.",
                chat_history=chat_history,
                seed=seed_value
            )
            mock_create.assert_called_once()
            called_with_params = mock_create.call_args[1]
            assert called_with_params['seed'] == seed_value

    def test_openai_prompt_with_function(
            self, open_ai_connection, example_prompt_template_with_function, functions):
        result = chat(
            connection=open_ai_connection,
            prompt=example_prompt_template_with_function,
            model="gpt-3.5-turbo",
            temperature=0,
            # test input functions.
            functions=functions,
            # test input prompt containing function role.
            name="get_location",
            result=json.dumps({"location": "Austin"}),
            question="What is the weather in Boston?",
            prev_question="Where is Boston?"
        )
        assert result["function_call"]["name"] == "get_current_weather"

    def test_openai_chat_with_response_format(self, open_ai_connection, example_prompt_template, chat_history):
        result = chat(
            connection=open_ai_connection,
            prompt=example_prompt_template,
            model="gpt-4-1106-preview",
            temperature=0,
            user_input="Write a slogan for product X, please reponse with json.",
            chat_history=chat_history,
            response_format={"type": "json_object"}
        )
        assert "Product X".lower() in result.lower()

    @pytest.mark.parametrize(
        "response_format, user_input, error_message, error_codes, exception",
        [
            ({"type": "json"}, "Write a slogan for product X, please reponse with json.",
             "\'json\' is not one of [\'json_object\', \'text\']", "UserError/OpenAIError/BadRequestError",
             WrappedOpenAIError),
            ({"type": "json_object"}, "Write a slogan for product X",
             "\'messages\' must contain the word \'json\' in some form", "UserError/OpenAIError/BadRequestError",
             WrappedOpenAIError),
            ({"types": "json_object"}, "Write a slogan for product X",
             "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}",
             "UserError/OpenAIError/BadRequestError",
             WrappedOpenAIError)
        ]
    )
    def test_openai_chat_with_invalid_response_format(
            self,
            open_ai_connection,
            example_prompt_template,
            chat_history,
            response_format,
            user_input,
            error_message,
            error_codes,
            exception
    ):
        with pytest.raises(exception) as exc_info:
            chat(
                connection=open_ai_connection,
                prompt=example_prompt_template,
                model="gpt-4-1106-preview",
                temperature=0,
                user_input=user_input,
                chat_history=chat_history,
                response_format=response_format
            )
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_openai_chat_with_not_support_response_format_json_mode_model(
            self,
            open_ai_connection,
            example_prompt_template,
            chat_history
    ):
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(
                connection=open_ai_connection,
                prompt=example_prompt_template,
                model="gpt-3.5-turbo",
                temperature=0,
                user_input="Write a slogan for product X, please reponse with json.",
                chat_history=chat_history,
                response_format={"type": "json_object"}
            )
        error_message = "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}."
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == "UserError/OpenAIError/BadRequestError".split("/")

    def test_openai_chat_with_response_format_text_mode(
            self,
            open_ai_connection,
            example_prompt_template,
            chat_history
    ):
        result = chat(
            connection=open_ai_connection,
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            temperature=0,
            user_input="Write a slogan for product X.",
            chat_history=chat_history,
            response_format={"type": "text"}
        )
        assert "Product X".lower() in result.lower()
