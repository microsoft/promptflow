import json
from unittest.mock import patch

import pytest
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.tools.exception import WrappedOpenAIError
from promptflow.tools.llm import llm

from tests.utils import AttrDict


@pytest.mark.usefixtures("use_secrets_config_file")
class TestLLM:
    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, params",
        [
            # test whether tool can handle param "stop" with value empty list
            # as openai raises "[] is not valid under any of the given schemas - 'stop'"
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-instruct", {"stop": [], "logit_bias": {}}),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-instruct", {},
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            # test completion stream
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-instruct",
                         {"stop": [], "logit_bias": {}, "stream": True}),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-instruct", {"stream": True},
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_completion(self, request, connection_type, model_or_deployment_name, params):
        connection = request.getfixturevalue(connection_type)
        prompt_template = "please complete this sentence: world war II "
        llm(
            connection=connection,
            api="completion",
            prompt=prompt_template,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            **params
        )

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, params",
        [
            pytest.param("azure_open_ai_connection", "gpt-35-turbo",
                         {"max_tokens": "inf", "temperature": 0, "user_input": "Fill in more details about trend 2.",
                          "seed": 123}),
            pytest.param("open_ai_connection", "gpt-3.5-turbo",
                         {"max_tokens": 32, "temperature": 0, "user_input": "Fill in more details about trend 2.",
                          "seed": 123}, marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            pytest.param("serverless_connection", None, {"user_input": "Fill in more details about trend 2."},
                         marks=pytest.mark.skip_if_no_api_key("serverless_connection")),
        ]
    )
    def test_llm_chat(self, request, connection_type, model_or_deployment_name, example_prompt_template, chat_history,
                      params):
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt=example_prompt_template,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            chat_history=chat_history,
            **params
        )
        assert "trend 2".lower() in result.lower()

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, params, expected_message",
        [
            pytest.param("azure_open_ai_connection", "gpt-35-turbo",
                         {"max_tokens": "32", "temperature": 0, "user_input": "Fill in more details about trend 2.",
                          "stream": True}, "additional details"),
            pytest.param("open_ai_connection", "gpt-3.5-turbo",
                         {"max_tokens": 32, "temperature": 0, "user_input": "Fill in more details about trend 2.",
                          "stream": True}, "trend 2", marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_stream_chat(self, request, connection_type, model_or_deployment_name, example_prompt_template,
                             chat_history, params, expected_message):
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt=example_prompt_template,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            chat_history=chat_history,
            **params
        )
        answer = ""
        while True:
            try:
                answer += next(result)
            except Exception:
                break
        assert expected_message in answer.lower()

    @pytest.mark.parametrize(
        "connection_type",
        [
            pytest.param("azure_open_ai_connection"),
            pytest.param("open_ai_connection", marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_correctly_pass_params(self, request, connection_type, example_prompt_template, chat_history):
        seed_value = 123
        with patch("openai.resources.chat.Completions.create") as mock_create:
            llm(
                connection=request.getfixturevalue(connection_type),
                api="chat",
                prompt=example_prompt_template,
                max_tokens="32",
                temperature=0,
                user_input="Fill in more details about trend 2.",
                chat_history=chat_history,
                seed=seed_value
            )

            mock_create.assert_called_once()
            called_with_params = mock_create.call_args[1]
            assert called_with_params['seed'] == seed_value

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, tool_choice",
        [
            pytest.param("azure_open_ai_connection", "gpt-35-turbo", "auto"),
            pytest.param("azure_open_ai_connection", "gpt-35-turbo",
                         {"type": "function", "function": {"name": "get_current_weather"}}),
            pytest.param("open_ai_connection", "gpt-3.5-turbo", "auto",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            pytest.param("open_ai_connection", "gpt-3.5-turbo",
                         {"type": "function", "function": {"name": "get_current_weather"}},
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ],
    )
    def test_llm_chat_with_tools(
            self, request, connection_type, model_or_deployment_name, example_prompt_template, chat_history, tools,
            tool_choice):
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt=example_prompt_template,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            max_tokens="inF",
            temperature=0,
            user_input="What is the weather in Boston?",
            chat_history=chat_history,
            tools=tools,
            tool_choice=tool_choice
        )
        assert "tool_calls" in result
        assert result["tool_calls"][0]["function"]["name"] == "get_current_weather"

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, prompt",
        [
            pytest.param("azure_open_ai_connection", "gpt-35-turbo", "example_prompt_template_with_name_in_roles"),
            pytest.param("open_ai_connection", "gpt-3.5-turbo", "example_prompt_template_with_function",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection"))
        ],
    )
    def test_llm_chat_with_name_in_roles(
            self, request, connection_type, model_or_deployment_name, prompt, chat_history, tools):
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt=request.getfixturevalue(prompt),
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            max_tokens="inF",
            temperature=0,
            tools=tools,
            name="get_location",
            result=json.dumps({"location": "Austin"}),
            question="What is the weather in Boston?",
            prev_question="Where is Boston?"
        )
        assert "tool_calls" in result
        assert result["tool_calls"][0]["function"]["name"] == "get_current_weather"

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name",
        [
            pytest.param("azure_open_ai_connection", "gpt-35-turbo"),
            pytest.param("open_ai_connection", "gpt-3.5-turbo",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_chat_message_with_no_content(self, request, connection_type, model_or_deployment_name):
        # missing colon after role name. Sometimes following prompt may result in empty content.
        connection = request.getfixturevalue(connection_type)
        prompt = (
            "user:\n what is your name\nassistant\nAs an AI language model developed by"
            " OpenAI, I do not have a name. You can call me OpenAI or AI assistant. "
            "How can I assist you today?"
        )
        # assert chat tool can handle.
        llm(
            connection=connection,
            api="chat",
            prompt=prompt,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
        )
        # empty content after role name:\n
        prompt = "user:\n"
        llm(
            connection=connection,
            api="chat",
            prompt=prompt,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
        )

    @pytest.mark.parametrize(
        "params, expected",
        [
            ({"stop": [], "logit_bias": {}}, {"stop": None}),
            ({"stop": ["</i>"], "logit_bias": {"16": 100, "17": 100}}, {}),
        ],
    )
    def test_llm_parameters(self, params, expected):
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
            result = llm(
                connection=conn,
                api="completion",
                prompt=prompt,
                deployment_name=deployment_name,
                **params
            )
            assert result == prompt

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, response_format, expected_message",
        [
            # test response_format with json_object value
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-1106", {"type": "json_object"}, "x:"),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-1106", {"type": "json_object"}, "x:",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            # test response_format with text value for models which not support response_format,
            pytest.param("azure_open_ai_connection", "gpt-35-turbo", {"type": "text"}, "Product X"),
            pytest.param("open_ai_connection", "gpt-3.5-turbo", {"type": "text"}, "Product X",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_chat_with_response_format(self, request, connection_type, model_or_deployment_name, response_format,
                                           example_prompt_template, chat_history, expected_message):
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt=example_prompt_template,
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            temperature=0,
            user_input="Write a slogan for product X, please response with json.",
            chat_history=chat_history,
            response_format=response_format
        )
        assert str(expected_message).lower() in result.lower()

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name, response_format, user_input, error_message, error_codes, exception",
        [
            # test invalid response_format value
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-1106", {"type": "json"},
                         "Write a slogan for product X, please response with json.",
                         "\'json\' is not one of [\'json_object\', \'text\']", "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-1106", {"type": "json"},
                         "Write a slogan for product X, please reponse with json.",
                         "\'json\' is not one of [\'json_object\', \'text\']", "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError, marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            # test no json string in prompt
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-1106", {"type": "json_object"},
                         "Write a slogan for product X",
                         "\'messages\' must contain the word \'json\' in some form",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-1106", {"type": "json_object"},
                         "Write a slogan for product X",
                         "\'messages\' must contain the word \'json\' in some form",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError, marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            # test invalid key in response_format value
            pytest.param("azure_open_ai_connection", "gpt-35-turbo-1106", {"types": "json_object"},
                         "Write a slogan for product X",
                         "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError),
            pytest.param("open_ai_connection", "gpt-3.5-turbo-1106", {"types": "json_object"},
                         "Write a slogan for product X",
                         "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError, marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
            # test not support response format json mode model
            pytest.param("azure_open_ai_connection", "gpt-35-turbo", {"types": "json_object"},
                         "Write a slogan for product X",
                         "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError),
            pytest.param("open_ai_connection", "gpt-3.5-turbo", {"types": "json_object"},
                         "Write a slogan for product X",
                         "The response_format parameter needs to be a dictionary such as {\"type\": \"text\"}.",
                         "UserError/OpenAIError/BadRequestError",
                         WrappedOpenAIError, marks=pytest.mark.skip_if_no_api_key("open_ai_connection"))
        ]
    )
    def test_llm_chat_with_response_format_error(
            self,
            request,
            connection_type,
            model_or_deployment_name,
            example_prompt_template,
            chat_history,
            response_format,
            user_input,
            error_message,
            error_codes,
            exception
    ):
        with pytest.raises(exception) as exc_info:
            connection = request.getfixturevalue(connection_type)
            llm(
                connection=connection,
                api="chat",
                prompt=example_prompt_template,
                deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
                model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
                temperature=0,
                user_input=user_input,
                chat_history=chat_history,
                response_format=response_format
            )
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.parametrize(
        "connection_type, model_or_deployment_name",
        [
            pytest.param("azure_open_ai_connection", "gpt-4v"),
            pytest.param("open_ai_connection", "gpt-4-vision-preview",
                         marks=pytest.mark.skip_if_no_api_key("open_ai_connection")),
        ]
    )
    def test_llm_with_vision_model(self, request, connection_type, model_or_deployment_name):
        # The issue https://github.com/microsoft/promptflow/issues/1683 is fixed
        connection = request.getfixturevalue(connection_type)
        result = llm(
            connection=connection,
            api="chat",
            prompt="user:\nhello",
            deployment_name=model_or_deployment_name if isinstance(connection, AzureOpenAIConnection) else None,
            model=model_or_deployment_name if isinstance(connection, OpenAIConnection) else None,
            stop=None,
            logit_bias={}
        )
        assert "hello" in result.lower() or "you" in result.lower()

    # the test is to verify the tool can support serving streaming functionality.
    def test_streaming_option_parameter_is_set(self):
        assert getattr(llm, "_streaming_option_parameter") == "stream"
