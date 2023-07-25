import pytest
import json

from promptflow.connections import OpenAIConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools.openai import embedding, chat, completion, OpenAI


@pytest.fixture
def open_ai_connection() -> [OpenAIConnection]:
    return ConnectionManager().get("open_ai_connection")


@pytest.fixture
def openai_provider(open_ai_connection) -> OpenAI:
    aoai_provider = OpenAI.from_config(open_ai_connection)
    return aoai_provider


@pytest.mark.usefixtures("use_secrets_config_file",
                         "open_ai_connection")
@pytest.mark.skip(reason="openai key not set yet")
class TestOpenAI:
    def test_openai_embedding_api(self, open_ai_connection):
        input = ["The food was delicious and the waiter"]  # we could use array as well, vs str
        result = embedding(open_ai_connection, input=input, model="text-embedding-ada-002")
        embedding_vector = ", ".join(str(num) for num in result)
        print("embedding() api result=[" + embedding_vector + "]")

    def test_openai_completion(self, openai_provider):
        prompt_template = "please complete this sentence: world war II "
        result = openai_provider.completion(prompt=prompt_template)
        print("openai.completion() result=[" + result + "]")

    def test_openai_completion_api(self, open_ai_connection):
        prompt_template = "please complete this sentence: world war II "
        result = completion(open_ai_connection, prompt=prompt_template)
        print("completion() api result=[" + result + "]")

    def test_openai_chat(self, openai_provider, example_prompt_template, chat_history):
        result = openai_provider.chat(
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            max_tokens=32,
            temperature=0,
            user_input="Fill in more detalis about trend 2.",
            chat_history=chat_history,
        )
        print("openai.chat() result=[" + result + "]")

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
        print("chat() api result=[" + result + "]")

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
            connection=open_ai_connection,
            prompt=example_prompt_template,
            model="gpt-3.5-turbo",
            max_tokens="inF",
            temperature=0,
            user_input="What is the weather in Boston?",
            chat_history=chat_history,
            function_call="auto",
            functions=functions
        )
        result = str(result.to_dict())
        print("chat() api result=[" + result + "]")

    def test_openai_embedding(self, openai_provider):
        input = "The food was delicious and the waiter"
        result = openai_provider.embedding(input=input)
        embedding_vector = ", ".join(str(num) for num in result)
        print("openai.embedding() result=[" + embedding_vector + "]")

    def test_openai_prompt_with_function(self, open_ai_connection, example_prompt_template_with_function):
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
            connection=open_ai_connection,
            prompt=example_prompt_template_with_function,
            model="gpt-3.5-turbo",
            temperature=0,
            functions=functions,
            name="get_location",
            result=json.dumps({"location": "Austin"}),
            # assignments=assignments,
            question="What is the weather in Boston?",
            prev_question="Where is Boston?"
        )
        assert result["function_call"]["name"] == "get_current_weather"
