import pytest
import json

from promptflow.tools.openai import chat, completion, OpenAI


@pytest.fixture
def openai_provider(open_ai_connection) -> OpenAI:
    return OpenAI(open_ai_connection)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip_if_no_key("open_ai_connection")
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
        )
        assert "details about trend 2" in result.lower()

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
        assert "details about trend 2" in answer.lower()

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
