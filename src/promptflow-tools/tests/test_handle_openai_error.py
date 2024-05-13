import httpx
import pytest
from unittest.mock import patch
from jinja2.exceptions import TemplateSyntaxError
from openai import (
    APIConnectionError,
    RateLimitError,
    AuthenticationError,
    BadRequestError,
    APITimeoutError, InternalServerError, UnprocessableEntityError
)
from promptflow.tools.aoai import chat, completion
from promptflow.tools.common import handle_openai_error
from promptflow.tools.exception import ChatAPIInvalidRole, WrappedOpenAIError, to_openai_error_message, \
    JinjaTemplateError, LLMError, ChatAPIFunctionRoleInvalidFormat, ExceedMaxRetryTimes
from promptflow.tools.openai import chat as openai_chat
from promptflow.tools.aoai_gpt4v import AzureOpenAI as AzureOpenAIVision
from pytest_mock import MockerFixture

from promptflow.exceptions import UserErrorException
from tests.utils import Deployment


@pytest.mark.usefixtures("use_secrets_config_file")
class TestHandleOpenAIError:
    def test_aoai_chat_message_invalid_format(self, aoai_provider):
        # chat api prompt should follow the format of "system:\nmessage1\nuser:\nmessage2".
        prompt = "what is your name"
        error_codes = "UserError/ToolValidationError/ChatAPIInvalidRole"
        with pytest.raises(ChatAPIInvalidRole,
                           match="The Chat API requires a specific format for prompt") as exc_info:
            aoai_provider.chat(prompt=prompt, deployment_name="gpt-35-turbo")
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_authentication_error_with_bad_api_key(self, azure_open_ai_connection):
        azure_open_ai_connection.api_key = "hello"
        prompt_template = "please complete this sentence: world war II "
        raw_message = (
            "Unauthorized. Access token is missing, invalid"
        )
        error_codes = "UserError/OpenAIError/AuthenticationError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_connection_error_with_bad_api_base(self, azure_open_ai_connection):
        azure_open_ai_connection.api_base = "https://gpt-test-eus11.openai.azure.com/"
        prompt_template = "please complete this sentence: world war II "
        error_codes = "UserError/OpenAIError/APIConnectionError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert "Connection error." in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_not_found_error_with_bad_api_version(self, azure_open_ai_connection):
        """NotFoundError: Resource not found"""
        azure_open_ai_connection.api_version = "2022-12-23"
        prompt_template = "please complete this sentence: world war II "
        raw_message = "Resource not found"
        error_codes = "UserError/OpenAIError/NotFoundError"
        # Chat will throw: Exception occurs: NotFoundError: Resource not found
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_not_found_error_with_bad_deployment(self, aoai_provider):
        """
        NotFoundError: The API deployment for this resource does not exist.
        If you created the deployment within the last 5 minutes, please wait a moment and try again.
        """
        # This will throw InvalidRequestError
        prompt_template = "please complete this sentence: world war II "
        deployment = "hello"
        raw_message = (
            "The API deployment for this resource does not exist. If you created the deployment "
            "within the last 5 minutes, please wait a moment and try again."
        )
        error_codes = "UserError/OpenAIError/NotFoundError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            aoai_provider.chat(prompt=f"user:\n{prompt_template}", deployment_name=deployment)
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_rate_limit_error_insufficient_quota(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = RateLimitError("Something went wrong", response=httpx.Response(
            429, request=httpx.Request('GET', 'https://www.example.com')), body={"type": "insufficient_quota"})
        mock_method = mocker.patch("openai.resources.Completions.create", side_effect=dummyEx)
        error_codes = "UserError/OpenAIError/RateLimitError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="text-ada-001")
        assert to_openai_error_message(dummyEx) == exc_info.value.message
        assert mock_method.call_count == 1
        assert exc_info.value.error_codes == error_codes.split("/")

    def create_api_connection_error_with_cause():
        error = APIConnectionError(
            request=httpx.Request('GET', 'https://www.example.com')
        )
        error.__cause__ = Exception("Server disconnected without sending a response.")
        return error

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError("Something went wrong", response=httpx.Response(
                        429, request=httpx.Request('GET', 'https://www.example.com')), body=None),
                    APITimeoutError(request=httpx.Request('GET', 'https://www.example.com')),
                    APIConnectionError(
                        message="('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))",
                        request=httpx.Request('GET', 'https://www.example.com')),
                    create_api_connection_error_with_cause(),
                    InternalServerError("Something went wrong", response=httpx.Response(
                        503, request=httpx.Request('GET', 'https://www.example.com')), body=None),
                ]
            ),
        ],
    )
    def test_retriable_openai_error_handle(self, mocker: MockerFixture, dummyExceptionList):
        for dummyEx in dummyExceptionList:
            # Patch the test_method to throw the desired exception
            patched_test_method = mocker.patch("openai.resources.Completions.create", side_effect=dummyEx)

            # Apply the retry decorator to the patched test_method
            max_retry = 2
            decorated_test_method = handle_openai_error(tries=max_retry)(patched_test_method)
            mock_sleep = mocker.patch("time.sleep")  # Create a separate mock for time.sleep

            with pytest.raises(UserErrorException) as exc_info:
                decorated_test_method()

            assert patched_test_method.call_count == max_retry + 1
            assert "Exceed max retry times. " + to_openai_error_message(dummyEx) == exc_info.value.message
            error_codes = "UserError/OpenAIError/" + type(dummyEx).__name__
            assert exc_info.value.error_codes == error_codes.split("/")
            expected_calls = [
                mocker.call(3),
                mocker.call(4),
            ]
            mock_sleep.assert_has_calls(expected_calls)

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError("Something went wrong", response=httpx.Response(
                        429, request=httpx.Request('GET', 'https://www.example.com'), headers={"retry-after": "0.3"}),
                                   body=None),
                    InternalServerError("Something went wrong", response=httpx.Response(
                        503, request=httpx.Request('GET', 'https://www.example.com'), headers={"retry-after": "0.3"}),
                                        body=None),
                ]
            ),
        ],
    )
    def test_retriable_openai_error_handle_with_header(
            self, mocker: MockerFixture, dummyExceptionList
    ):
        for dummyEx in dummyExceptionList:
            # Patch the test_method to throw the desired exception
            patched_test_method = mocker.patch("promptflow.tools.aoai.completion", side_effect=dummyEx)

            # Apply the retry decorator to the patched test_method
            max_retry = 2
            header_delay = 0.3
            decorated_test_method = handle_openai_error(tries=max_retry)(patched_test_method)
            mock_sleep = mocker.patch("time.sleep")  # Create a separate mock for time.sleep

            with pytest.raises(UserErrorException) as exc_info:
                decorated_test_method()

            assert patched_test_method.call_count == max_retry + 1
            assert "Exceed max retry times. " + to_openai_error_message(dummyEx) == exc_info.value.message
            error_codes = "UserError/OpenAIError/" + type(dummyEx).__name__
            assert exc_info.value.error_codes == error_codes.split("/")
            expected_calls = [
                mocker.call(header_delay),
                mocker.call(header_delay),
            ]
            mock_sleep.assert_has_calls(expected_calls)

    def test_unprocessable_entity_error(self, mocker: MockerFixture):
        unprocessable_entity_error = UnprocessableEntityError(
            "Something went wrong", response=httpx.Response(
                422, request=httpx.Request('GET', 'https://www.example.com')), body=None)
        rate_limit_error = RateLimitError("Something went wrong", response=httpx.Response(
            429, request=httpx.Request('GET', 'https://www.example.com'), headers={"retry-after": "0.3"}),
            body=None)
        # for below exception sequence, "consecutive_422_error_count" changes: 0 -> 1 -> 0 -> 1 -> 2.
        exception_sequence = [
            unprocessable_entity_error, rate_limit_error, unprocessable_entity_error, unprocessable_entity_error]
        patched_test_method = mocker.patch("promptflow.tools.aoai.AzureOpenAI.chat", side_effect=exception_sequence)
        # limit api connection error retry threshold to 2.
        decorated_test_method = handle_openai_error(unprocessable_entity_error_tries=2)(patched_test_method)
        with pytest.raises(ExceedMaxRetryTimes):
            decorated_test_method()
        assert patched_test_method.call_count == 4

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    AuthenticationError("Something went wrong", response=httpx.get('https://www.example.com'),
                                        body=None),
                    BadRequestError("Something went wrong", response=httpx.get('https://www.example.com'),
                                    body=None),
                ]
            ),
        ],
    )
    def test_non_retriable_openai_error_handle(
            self, azure_open_ai_connection, mocker: MockerFixture, dummyExceptionList
    ):
        for dummyEx in dummyExceptionList:
            mock_method = mocker.patch("openai.resources.Completions.create", side_effect=dummyEx)
            with pytest.raises(UserErrorException) as exc_info:
                completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="text-ada-001")
            assert to_openai_error_message(dummyEx) == exc_info.value.message
            error_codes = "UserError/OpenAIError/" + type(dummyEx).__name__
            assert exc_info.value.error_codes == error_codes.split("/")
            assert mock_method.call_count == 1

    def test_unexpected_error_handle(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = Exception("Something went wrong")
        chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-35-turbo")
        mock_method = mocker.patch("openai.resources.chat.Completions.create", side_effect=dummyEx)
        error_codes = "UserError/LLMError"

        with pytest.raises(LLMError) as exc_info:
            chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-35-turbo")
        assert to_openai_error_message(dummyEx) != exc_info.value.args[0]
        assert "OpenAI API hits exception: Exception: Something went wrong" == exc_info.value.message
        assert mock_method.call_count == 1
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_template_syntax_error_handle(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = TemplateSyntaxError(message="Something went wrong", lineno=1)
        mock_method = mocker.patch("jinja2.Template.__new__", side_effect=dummyEx)
        error_codes = "UserError/ToolValidationError/JinjaTemplateError"
        with pytest.raises(JinjaTemplateError) as exc_info:
            chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-35-turbo")
        error_message = "Failed to render jinja template: TemplateSyntaxError: Something went wrong\n  line 1. " \
                        + "Please modify your prompt to fix the issue."
        assert error_message == exc_info.value.message
        assert mock_method.call_count == 1
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skip_if_no_api_key("open_ai_connection")
    def test_model_not_accept_functions_as_param(
            self, open_ai_connection, example_prompt_template, functions):
        with pytest.raises(WrappedOpenAIError) as exc_info:
            openai_chat(
                connection=open_ai_connection,
                prompt=example_prompt_template,
                model="gpt-3.5-turbo-0301",
                functions=functions
            )
        assert "Current model does not support the `functions` parameter" in exc_info.value.message

    def test_input_invalid_function_role_prompt(self, azure_open_ai_connection):
        with pytest.raises(ChatAPIFunctionRoleInvalidFormat) as exc_info:
            chat(
                connection=azure_open_ai_connection,
                prompt="function:\n This is function role prompt",
                deployment_name="gpt-35-turbo"
            )
        assert "'name' is required if role is function," in exc_info.value.message

    @pytest.mark.skip(reason="Skip temporarily because there is something issue with test AOAI resource response.")
    def test_completion_with_chat_model(self, azure_open_ai_connection):
        with pytest.raises(UserErrorException) as exc_info:
            completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="gpt-35-turbo")
        msg = "Completion API is a legacy api and is going to be deprecated soon. " \
              "Please change to use Chat API for current model."
        assert msg in exc_info.value.message

    def test_model_not_support_image_input(
            self, azure_open_ai_connection, example_prompt_template_with_image, example_image):
        aoai = AzureOpenAIVision(azure_open_ai_connection)
        with pytest.raises(WrappedOpenAIError) as exc_info:
            aoai.chat(
                prompt=example_prompt_template_with_image,
                deployment_name="gpt-35-turbo",
                max_tokens=480,
                temperature=0,
                question="which number did you see in this picture?",
                image_input=example_image,
            )
        assert "Current model does not support the image input" in exc_info.value.message

    @pytest.mark.parametrize(
        "max_tokens, error_message, error_codes, exception",
        [
            (0, "0 is less than the minimum of 1", "UserError/OpenAIError/BadRequestError", WrappedOpenAIError),
            (-1, "-1 is less than the minimum of 1", "UserError/OpenAIError/BadRequestError", WrappedOpenAIError),
            ("asd", "ValueError: invalid literal for int()", "UserError/LLMError", LLMError)
        ]
    )
    def test_aoai_invalid_max_tokens(
            self,
            azure_open_ai_connection,
            example_prompt_template,
            chat_history,
            max_tokens,
            error_message,
            error_codes,
            exception):
        with pytest.raises(exception) as exc_info:
            chat(
                connection=azure_open_ai_connection,
                prompt=example_prompt_template,
                deployment_name="gpt-35-turbo",
                max_tokens=max_tokens,
                temperature=0,
                user_input="Write a slogan for product X",
                chat_history=chat_history,
            )
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skip("Skip this before we figure out how to make token provider work on github action")
    def test_authentication_fail_for_aoai_meid_token_connection(self, azure_open_ai_connection_meid):
        prompt_template = "please complete this sentence: world war II "
        raw_message = (
            "please make sure you have proper role assignment on your azure openai resource"
        )
        error_codes = "UserError/OpenAIError/AuthenticationError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection_meid, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_aoai_with_vision_model_extra_fields_error(self, azure_open_ai_connection):
        with (
            patch('promptflow.tools.common.get_workspace_triad') as mock_get,
            patch('promptflow.tools.common.list_deployment_connections') as mock_list,
            pytest.raises(LLMError) as exc_info
        ):
            mock_get.return_value = ("sub", "rg", "ws")
            mock_list.return_value = {
                Deployment("gpt-4v", "model1", "vision-preview"),
                Deployment("deployment2", "model2", "version2")
            }

            chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-4v",
                 response_format={"type": "text"})

        assert "extra fields not permitted" in exc_info.value.message
        assert "Please kindly avoid using vision model in LLM tool" in exc_info.value.message

    @pytest.mark.parametrize(
        "prompt_template",
        [
            (
                """
                    # assistant:
                    How can I assist you?

                    # tool:
                    ## tool_call_id:
                    fake_tool_call_id
                    ## content:
                    fake_content
                """
            ),
            (
                """
                    # assistant:
                    ## tool_calls:
                    [{'id': 'fake_tool_id', 'type': 'function', 'function': {'name': 'f_n', 'arguments': '{}'}}]

                    # tool_1:
                    ## tool_call_id:
                    fake_tool_call_id
                    ## content:
                    fake_content
                """
            ),
        ],
    )
    def test_chat_prompt_with_invalid_tool_message(self, azure_open_ai_connection, prompt_template):
        error_codes = "UserError/OpenAIError/BadRequestError"
        raw_message = (
            "Please make sure your chat prompt includes 'tool_calls' within the 'assistant' role. Also, the "
            "assistant message must be followed by messages with role 'tool', matching ids of assistant message "
            "'tool_calls' property. You could refer to guideline at https://aka.ms/pfdoc/chat-prompt"
        )
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"{prompt_template}", deployment_name="gpt-35-turbo")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")
