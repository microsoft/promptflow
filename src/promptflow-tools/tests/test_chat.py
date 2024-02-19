import pytest

from promptflow.tools.chat import chat
from promptflow.tools.exception import InvalidConnectionType


@pytest.mark.usefixtures("use_secrets_config_file")
class TestChat:
    def test_aoai(self, azure_open_ai_connection, example_prompt_template, chat_history):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo",
            input="The food was delicious and the waiter",
            user_input="Fill in more details about trend 2.",
            chat_history=chat_history)
        print(result)
        assert "details" in result.lower()

    def test_aoai_with_image(self, azure_open_ai_connection, example_prompt_template_with_image, example_image):
        result = chat(
            connection=azure_open_ai_connection,
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            input="The food was delicious and the waiter",
            question="which number did you see in this picture?",
            response_format={"type":"text"},
            image_input=example_image)
        print(result)
        assert "10" == result
