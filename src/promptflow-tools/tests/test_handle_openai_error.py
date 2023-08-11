import pytest
from jinja2.exceptions import TemplateSyntaxError
from openai.error import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    InvalidAPIType,
    InvalidRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pytest_mock import MockerFixture

from promptflow.exceptions import UserErrorException, ErrorResponse
from promptflow.tools.aoai import chat, completion

from promptflow.tools.common import handle_openai_error
from promptflow.tools.exception import ChatAPIInvalidRole, WrappedOpenAIError, openai_error_code_ref_message, \
    to_openai_error_message, JinjaTemplateError, LLMError, ChatAPIFunctionRoleInvalidFormat
from promptflow.tools.openai import chat as openai_chat


@pytest.mark.usefixtures("use_secrets_config_file")
class TestHandleOpenAIError:
    def test_aoai_chat_message_invalid_format(self, aoai_provider):
        # chat api prompt should follow the format of "system:\nmessage1\nuser:\nmessage2".
        prompt = "what is your name"
        with pytest.raises(ChatAPIInvalidRole,
                           match="The Chat API requires a specific format for prompt") as exc_info:
            aoai_provider.chat(prompt=prompt, deployment_name="gpt-35-turbo")
        assert "UserError/ToolValidationError/ChatAPIInvalidRole" == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_aoai_authencation_error_with_bad_api_key(self, azure_open_ai_connection):
        azure_open_ai_connection.api_key = "hello"
        prompt_template = "please complete this sentence: world war II "
        raw_message = (
            "Access denied due to invalid subscription key or wrong API endpoint. "
            "Make sure to provide a valid key for an active subscription and use a "
            "correct regional API endpoint for your resource."
        )
        error_msg = to_openai_error_message(AuthenticationError(message=raw_message))
        error_code = "UserError/OpenAIError/AuthenticationError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert error_msg == exc_info.value.message
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_aoai_connection_error_with_bad_api_base(self, azure_open_ai_connection):
        """
        APIConnectionError: Error communicating with OpenAI: HTTPSConnectionPool(host='gpt-test-eus11.openai.azure.com'
        , port=443): Max retries exceeded with url: //openai/deployments/text-ada-001/completions?
        api-version=2022-12-01 (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object
        at 0x000001A222CBC100>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed'))
        """
        azure_open_ai_connection.api_base = "https://gpt-test-eus11.openai.azure.com/"
        prompt_template = "please complete this sentence: world war II "
        error_code = "UserError/OpenAIError/APIConnectionError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert openai_error_code_ref_message in exc_info.value.message
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_aoai_invalid_request_error_with_bad_api_version(self, azure_open_ai_connection):
        """InvalidRequestError: Resource not found"""
        azure_open_ai_connection.api_version = "2022-12-23"
        prompt_template = "please complete this sentence: world war II "
        raw_message = "Resource not found"
        error_msg = to_openai_error_message(InvalidRequestError(message=raw_message, param=None))
        error_code = "UserError/OpenAIError/InvalidRequestError"
        # Chat will throw: Exception occurs: InvalidRequestError: Resource not found
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert error_msg == exc_info.value.message
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_aoai_invalid_request_error_with_bad_api_type(self, azure_open_ai_connection):
        """
        InvalidAPIType: The API type provided in invalid. Please select one of the supported API types:
        'azure', 'azure_ad', 'open_ai'
        """
        azure_open_ai_connection.api_type = "aml"
        prompt_template = "please complete this sentence: world war II "
        raw_message = (
            "The API type provided in invalid. Please select one of the supported API types: "
            "'azure', 'azure_ad', 'open_ai'"
        )
        error_msg = to_openai_error_message(InvalidAPIType(message=raw_message))
        error_code = "UserError/OpenAIError/InvalidAPIType"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            chat(azure_open_ai_connection, prompt=f"user:\n{prompt_template}", deployment_name="gpt-35-turbo")
        assert error_msg == exc_info.value.message
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_aoai_invalid_request_error_with_bad_deployment(self, aoai_provider):
        """
        InvalidRequestError: The API deployment for this resource does not exist.
        If you created the deployment within the last 5 minutes, please wait a moment and try again.
        """
        # This will throw InvalidRequestError
        prompt_template = "please complete this sentence: world war II "
        deployment = "hello"
        raw_message = (
            "The API deployment for this resource does not exist. If you created the deployment "
            "within the last 5 minutes, please wait a moment and try again."
        )
        error_msg = to_openai_error_message(InvalidRequestError(message=raw_message, param=None))
        error_code = "UserError/OpenAIError/InvalidRequestError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            aoai_provider.chat(prompt=f"user:\n{prompt_template}", deployment_name=deployment)
        assert error_msg == exc_info.value.message
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_rate_limit_error_insufficient_quota(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = RateLimitError("Something went wrong", json_body={"error": {"type": "insufficient_quota"}})
        mock_method = mocker.patch("promptflow.tools.aoai.openai.Completion.create", side_effect=dummyEx)
        error_code = "UserError/OpenAIError/RateLimitError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="text-ada-001")
        assert to_openai_error_message(dummyEx) == exc_info.value.message
        assert mock_method.call_count == 1
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_non_retriable_connection_error(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = APIConnectionError("Something went wrong")
        mock_method = mocker.patch("promptflow.tools.aoai.openai.Completion.create", side_effect=dummyEx)
        error_code = "UserError/OpenAIError/APIConnectionError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="text-ada-001")
        assert to_openai_error_message(dummyEx) == exc_info.value.message
        assert mock_method.call_count == 1
        assert error_code == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError("Something went wrong"),
                    ServiceUnavailableError("Something went wrong"),
                    APIError("Something went wrong"),
                    Timeout("Something went wrong"),
                    APIConnectionError("('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))")
                ]
            ),
        ],
    )
    def test_retriable_openai_error_handle(self, mocker: MockerFixture, dummyExceptionList):
        for dummyEx in dummyExceptionList:
            # Patch the test_method to throw the desired exception
            patched_test_method = mocker.patch("promptflow.tools.aoai.completion", side_effect=dummyEx)

            # Apply the retry decorator to the patched test_method
            max_retry = 2
            delay = 0.2
            decorated_test_method = handle_openai_error(tries=max_retry, delay=delay)(patched_test_method)
            mock_sleep = mocker.patch("time.sleep")  # Create a separate mock for time.sleep

            with pytest.raises(UserErrorException) as exc_info:
                decorated_test_method()

            assert patched_test_method.call_count == max_retry + 1
            assert "Exceed max retry times. " + to_openai_error_message(dummyEx) == exc_info.value.message
            assert "UserError/OpenAIError/" + type(dummyEx).__name__ == ErrorResponse.from_exception(
                exc_info.value).error_code_hierarchy
            expected_calls = [
                mocker.call(delay),
                mocker.call(delay * 2),
            ]
            mock_sleep.assert_has_calls(expected_calls)

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError("Something went wrong", headers={"Retry-After": "0.3"}),
                    ServiceUnavailableError("Something went wrong", headers={"Retry-After": "0.3"}),
                    APIError("Something went wrong", headers={"Retry-After": "0.3"}),
                    Timeout("Something went wrong", headers={"Retry-After": "0.3"}),
                    APIConnectionError("('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))",
                                       headers={"Retry-After": "0.3"})
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
            delay = 0.2
            header_delay = 0.3
            decorated_test_method = handle_openai_error(tries=max_retry, delay=delay)(patched_test_method)
            mock_sleep = mocker.patch("time.sleep")  # Create a separate mock for time.sleep

            with pytest.raises(UserErrorException) as exc_info:
                decorated_test_method()

            assert patched_test_method.call_count == max_retry + 1
            assert "Exceed max retry times. " + to_openai_error_message(dummyEx) == exc_info.value.message
            assert "UserError/OpenAIError/" + type(dummyEx).__name__ == ErrorResponse.from_exception(
                exc_info.value).error_code_hierarchy
            expected_calls = [
                mocker.call(header_delay),
                mocker.call(header_delay * 2),
            ]
            mock_sleep.assert_has_calls(expected_calls)

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    AuthenticationError("Something went wrong"),
                    APIConnectionError("Something went wrong"),
                    InvalidRequestError("Something went wrong", param=None),
                    InvalidAPIType("Something went wrong"),
                ]
            ),
        ],
    )
    def test_non_retriable_openai_error_handle(
            self, azure_open_ai_connection, mocker: MockerFixture, dummyExceptionList
    ):
        for dummyEx in dummyExceptionList:
            mock_method = mocker.patch("promptflow.tools.aoai.openai.Completion.create", side_effect=dummyEx)
            with pytest.raises(UserErrorException) as exc_info:
                completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="text-ada-001")
            assert to_openai_error_message(dummyEx) == exc_info.value.message
            assert "UserError/OpenAIError/" + type(dummyEx).__name__ == ErrorResponse.from_exception(
                exc_info.value).error_code_hierarchy
            assert mock_method.call_count == 1

    def test_unexpected_error_handle(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = Exception("Something went wrong")
        mock_method = mocker.patch("promptflow.tools.aoai.openai.ChatCompletion.create", side_effect=dummyEx)
        with pytest.raises(LLMError) as exc_info:
            chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-35-turbo")
        assert to_openai_error_message(dummyEx) != exc_info.value.args[0]
        assert "OpenAI API hits exception: Exception: Something went wrong" == exc_info.value.message
        assert mock_method.call_count == 1
        assert "UserError/LLMError" == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    def test_template_syntax_error_handle(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = TemplateSyntaxError(message="Something went wrong", lineno=1)
        mock_method = mocker.patch("jinja2.Template.__new__", side_effect=dummyEx)
        with pytest.raises(JinjaTemplateError) as exc_info:
            chat(connection=azure_open_ai_connection, prompt="user:\nhello", deployment_name="gpt-35-turbo")
        error_message = "Failed to render jinja template: TemplateSyntaxError: Something went wrong\n  line 1. " \
                        + "Please modify your prompt to fix the issue."
        assert error_message == exc_info.value.message
        assert mock_method.call_count == 1
        assert "UserError/ToolValidationError/JinjaTemplateError" == ErrorResponse.from_exception(
            exc_info.value).error_code_hierarchy

    @pytest.mark.skip_if_no_key("open_ai_connection")
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

    def test_completion_with_chat_model(self, azure_open_ai_connection):
        with pytest.raises(UserErrorException) as exc_info:
            completion(connection=azure_open_ai_connection, prompt="hello", deployment_name="gpt-4")
        msg = "OpenAI API hits InvalidRequestError: The completion operation only support some specified models, " \
              "please choose the model text-davinci-001, text-davinci-002,text-davinci-003, text-curie-001, text-babbage-001, " \
              "text-ada-001, code-cushman-001 or code-davinci-002 for completion operation."
        assert msg == exc_info.value.message
