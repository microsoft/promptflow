from unittest.mock import patch

import pytest
import json
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.aoai import chat, completion
from promptflow.tools.exception import WrappedOpenAIError
from tests.utils import AttrDict


@pytest.mark.usefixtures("use_secrets_config_file")
class TestAOAI:
    def test_aoai_completion(self, aoai_provider):
        prompt_template = "please complete this sentence: world war II "
        # test whether tool can handle param "stop" with value empty list
        # as openai raises "[] is not valid under any of the given schemas - 'stop'"
        aoai_provider.completion(
            prompt=prompt_template, deployment_name="gpt-35-turbo-16k", stop=[], logit_bias={}
        )

    def test_aoai_stream_completion(self, aoai_provider):
        prompt_template = "please complete this sentence: world war II "
        # test whether tool can handle param "stop" with value empty list in stream mode
        # as openai raises "[] is not valid under any of the given schemas - 'stop'"
        aoai_provider.completion(
            prompt=prompt_template, deployment_name="gpt-35-turbo-16k", stop=[], logit_bias={}, stream=True
        )

    def test_aoai_chat(self, aoai_provider, example_prompt_template, chat_history):
        result = aoai_provider.chat(
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-16k",
            max_tokens="32",
            temperature=0,
            user_input="Fill in more details about trend 2.",
            chat_history=chat_history,
        )
        assert "additional details" in result.lower()

    def test_aoai_chat_api(self, azure_open_ai_connection, example_prompt_template, chat_history):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-16k",
            max_tokens="inF",
            temperature=0,
            user_input="Write a slogan for product X",
            chat_history=chat_history,
        )
        assert "Product X".lower() in result.lower()

    @pytest.mark.parametrize(
        "function_call",
        [
            "auto",
            {"name": "get_current_weather"},
        ],
    )
    def test_aoai_chat_with_function(
            self, azure_open_ai_connection, example_prompt_template, chat_history, functions, function_call):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-16k",
            max_tokens="inF",
            temperature=0,
            user_input="What is the weather in Boston?",
            chat_history=chat_history,
            functions=functions,
            function_call=function_call
        )
        assert "function_call" in result
        assert result["function_call"]["name"] == "get_current_weather"

    def test_aoai_chat_with_name_in_roles(
            self, azure_open_ai_connection, example_prompt_template_with_name_in_roles, chat_history, functions):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template_with_name_in_roles,
            deployment_name="gpt-35-turbo-16k",
            max_tokens="inF",
            temperature=0,
            functions=functions,
            name="get_location",
            result=json.dumps({"location": "Austin"}),
            question="What is the weather in Boston?",
            prev_question="Where is Boston?"
        )
        assert "function_call" in result
        assert result["function_call"]["name"] == "get_current_weather"

    def test_aoai_chat_message_with_no_content(self, aoai_provider):
        # missing colon after role name. Sometimes following prompt may result in empty content.
        prompt = (
            "user:\n what is your name\nassistant\nAs an AI language model developed by"
            " OpenAI, I do not have a name. You can call me OpenAI or AI assistant. "
            "How can I assist you today?"
        )
        # assert chat tool can handle.
        aoai_provider.chat(prompt=prompt, deployment_name="gpt-35-turbo")
        # empty content after role name:\n
        prompt = "user:\n"
        aoai_provider.chat(prompt=prompt, deployment_name="gpt-35-turbo")

    def test_aoai_stream_chat(self, aoai_provider, example_prompt_template, chat_history):
        result = aoai_provider.chat(
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-16k",
            max_tokens="32",
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
        assert "additional details" in answer.lower()

    @pytest.mark.parametrize(
        "params, expected",
        [
            ({"stop": [], "logit_bias": {}}, {"stop": None}),
            ({"stop": ["</i>"], "logit_bias": {"16": 100, "17": 100}}, {}),
        ],
    )
    def test_aoai_parameters(self, params, expected):
        for k, v in params.items():
            if k not in expected:
                expected[k] = v
        deployment_name = "dummy"
        conn_dict = {"api_key": "dummy", "api_base": "base", "api_version": "dummy_ver", "api_type": "azure"}
        conn = AzureOpenAIConnection(**conn_dict)

        def mock_completion(self, **kwargs):
            assert kwargs["model"] == deployment_name
            for k, v in expected.items():
                assert kwargs[k] == v, f"Expect {k} to be {v}, but got {kwargs[k]}"
            text = kwargs["prompt"]
            return AttrDict({"choices": [AttrDict({"text": text})]})

        with patch("openai.resources.Completions.create", new=mock_completion):
            prompt = "dummy_prompt"
            result = completion(connection=conn, prompt=prompt, deployment_name=deployment_name, **params)
            assert result == prompt

    def test_aoai_chat_with_response_format(
            self,
            azure_open_ai_connection,
            example_prompt_template,
            chat_history):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-4",
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
    def test_aoai_chat_with_invalid_response_format(
            self,
            azure_open_ai_connection,
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
                connection=azure_open_ai_connection,
                prompt=example_prompt_template,
                deployment_name="gpt4",
                temperature=0,
                user_input=user_input,
                chat_history=chat_history,
                response_format=response_format
            )
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_chat_with_not_support_response_format_json_mode_model(
            self,
            azure_open_ai_connection,
            example_prompt_template,
            chat_history
    ):
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(
                connection=azure_open_ai_connection,
                prompt=example_prompt_template,
                deployment_name="gpt-35-turbo-16k",
                temperature=0,
                user_input="Write a slogan for product X, please reponse with json.",
                chat_history=chat_history,
                response_format={"type": "json_object"}
            )
        error_message = "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}."
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == "UserError/OpenAIError/BadRequestError".split("/")

    def test_aoai_chat_with_response_format_text_mode(
            self,
            azure_open_ai_connection,
            example_prompt_template,
            chat_history
    ):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-16k",
            temperature=0,
            user_input="Write a slogan for product X.",
            chat_history=chat_history,
            response_format={"type": "text"}
        )
        assert "Product X".lower() in result.lower()
