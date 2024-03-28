import pytest

from promptflow.tools.llm import llm
from promptflow.tools.exception import InvalidConnectionType


@pytest.mark.usefixtures("use_secrets_config_file")
class TestChat:
    def test_aoai(self, azure_open_ai_connection, example_prompt_template, chat_history):
        result = llm(
            connection=azure_open_ai_connection,
            api="completion",
            prompt=example_prompt_template,
            deployment_name="gpt-35-turbo-instruct",
            input="The food was delicious and the waiter",
            user_input="Fill in more details about trend 2.",
            chat_history=chat_history)
        print(result)
        assert "trend 2" in result.lower()

    # def test_aoai_with_image(self, azure_open_ai_connection, example_prompt_template_with_image, example_image):
    #     result = llm(
    #         connection=azure_open_ai_connection,
    #         prompt=example_prompt_template_with_image,
    #         deployment_name="gpt-4v",
    #         input="The food was delicious and the waiter",
    #         question="which number did you see in this picture?",
    #         response_format={"type":"text"},
    #         image_input=example_image)
    #     print(result)
    #     assert "10" == result

    # def test_gptv_function_call(self, azure_open_ai_connection, example_prompt_template_with_image, example_image, functions):
    #     result = llm(
    #         connection=azure_open_ai_connection,
    #         prompt=example_prompt_template_with_image,
    #         deployment_name="gpt-4v",
    #         input="The food was delicious and the waiter",
    #         question="which number did you see in this picture?",
    #         functions=functions,
    #         function_call="auto",
    #         image_input=example_image)
    #     print(result)