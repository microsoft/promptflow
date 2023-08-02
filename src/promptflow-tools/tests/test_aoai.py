from unittest.mock import patch

import pytest

from promptflow.connections import AzureOpenAIConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools.aoai import AzureOpenAI, chat, completion, embedding
from promptflow.utils.utils import AttrDict


@pytest.fixture
def azure_open_ai_connection() -> AzureOpenAIConnection:
    return ConnectionManager().get("azure_open_ai_connection")


@pytest.fixture
def aoai_provider(azure_open_ai_connection) -> AzureOpenAI:
    aoai_provider = AzureOpenAI(azure_open_ai_connection)
    return aoai_provider


@pytest.mark.usefixtures("use_secrets_config_file", "aoai_provider", "azure_open_ai_connection")
class TestAOAI:
    def test_aoai_completion(self, aoai_provider):
        prompt_template = "please complete this sentence: world war II "
        # test whether tool can handle param "stop" with value empty list
        # as openai raises "[] is not valid under any of the given schemas - 'stop'"
        result = aoai_provider.completion(
            prompt=prompt_template, deployment_name="text-ada-001", stop=[], logit_bias={}
        )
        print("aoai.completion() result=[" + result + "]")

    def test_aoai_chat(self, aoai_provider, example_prompt_template, chat_history):
        result = aoai_provider.chat(
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo",
            max_tokens="32",
            temperature=0,
            user_input="Fill in more detalis about trend 2.",
            chat_history=chat_history,
        )
        print("aoai.chat() result=[" + result + "]")
        assert "details about trend 2" in result.lower()

    def test_aoai_chat_api(self, azure_open_ai_connection, example_prompt_template, chat_history):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo",
            max_tokens="inF",
            temperature=0,
            user_input="Write a slogan for product X",
            chat_history=chat_history,
        )
        print(" chat() api result=[" + result + "]")
        assert "Product X".lower() in result.lower()

        functions = [
            {
                "name": "get_current_weather",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            }
        ]

        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo",
            max_tokens="inF",
            temperature=0,
            user_input="What is the weather in Boston?",
            chat_history=chat_history,
            functions=functions,
            function_call="auto"
        )
        result = str(result.to_dict())
        print(" chat() api result=[" + result + "]")

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

    def test_aoai_embedding(self, aoai_provider):
        input = "The food was delicious and the waiter"
        result = aoai_provider.embedding(input=input, deployment_name="text-embedding-ada-002")
        embedding_vector = ", ".join(str(num) for num in result)
        print("aoai.embedding() result=[" + embedding_vector + "]")

    def test_aoai_embedding_api(self, azure_open_ai_connection):
        input = ["The food was delicious and the waiter"]  # we could use array as well, vs str
        result = embedding(azure_open_ai_connection, input=input, deployment_name="text-embedding-ada-002")
        embedding_vector = ", ".join(str(num) for num in result)
        print("embedding() api result=[" + embedding_vector + "]")

    def test_chat_no_exception_even_no_message_content(self, aoai_provider):
        # This is to confirm no exception even if no message content; For more details, please find
        # https://msdata.visualstudio.com/Vienna/_workitems/edit/2377116
        prompt = (
            "user:\n what is your name\nassistant\nAs an AI language model developed by OpenAI, "
            "I do not have a name. You can call me OpenAI or AI assistant. How can I assist you today?"
        )

        result = aoai_provider.chat(prompt=prompt, deployment_name="gpt-35-turbo")
        print("test_chat_no_exception_even_no_message_content result=[" + result + "]")

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

        def mock_completion(**kwargs):
            assert kwargs["engine"] == deployment_name
            for k, v in expected.items():
                assert kwargs[k] == v, f"Expect {k} to be {v}, but got {kwargs[k]}"
            for k, v in conn_dict.items():
                assert kwargs[k] == v, f"Expect {k} to be {v}, but got {kwargs[k]}"
            text = kwargs["prompt"]
            return AttrDict({"choices": [AttrDict({"text": text})]})

        with patch("openai.Completion.create", new=mock_completion):
            prompt = "dummy_prompt"
            result = completion(connection=conn, prompt=prompt, deployment_name=deployment_name, **params)
            assert result == prompt
