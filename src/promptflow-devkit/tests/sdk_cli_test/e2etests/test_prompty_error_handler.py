from unittest.mock import AsyncMock

import httpx
import pytest
from _constants import PROMPTFLOW_ROOT
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
    UnprocessableEntityError,
)
from pytest_mock import MockerFixture

from promptflow.core import Prompty
from promptflow.core._errors import (
    ChatAPIInvalidRoleError,
    ExceedMaxRetryTimes,
    LLMError,
    WrappedOpenAIError,
    to_openai_error_message,
)
from promptflow.core._prompty_utils import handle_openai_error, handle_openai_error_async
from promptflow.exceptions import UserErrorException

PROMPTY_FOLDER = PROMPTFLOW_ROOT / "tests" / "test_configs" / "prompty"


def load_prompty(connection, configuration=None, parameters=None):
    model_dict = {
        "configuration": {
            "type": "azure_openai",
            "azure_deployment": "gpt-35-turbo",
            "api_key": connection.api_key,
            "api_version": connection.api_version,
            "azure_endpoint": connection.api_base,
            "connection": None,
        },
    }
    if configuration:
        model_dict["configuration"].update(configuration)
    if parameters:
        model_dict["parameters"] = parameters
    return Prompty.load(
        source=PROMPTY_FOLDER / "prompty_example.prompty",
        model=model_dict,
    )


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "recording_injection")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestHandlePromptyError:
    def test_chat_message_invalid_format(self):
        # chat api prompt should follow the format of "system:\nmessage1\nuser:\nmessage2".
        error_codes = "UserError/CoreError/ChatAPIInvalidRoleError"
        prompty = Prompty.load(source=PROMPTY_FOLDER / "prompty_example.prompty")
        with pytest.raises(
            ChatAPIInvalidRoleError, match="The Chat API requires a specific format for prompt"
        ) as exc_info:
            prompty._template = "what is your name"
            prompty(question="what is the result of 1+1?")
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skipif(pytest.is_replay, reason="The successfully submitted record is referenced in record mode.")
    def test_authentication_error_with_bad_api_key(self, azure_open_ai_connection):
        raw_message = "Unauthorized. Access token is missing, invalid"
        error_codes = "UserError/OpenAIError/AuthenticationError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            prompty = load_prompty(connection=azure_open_ai_connection, configuration={"api_key": "mock_api_key"})
            prompty(question="what is the result of 1+1?")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skipif(pytest.is_replay, reason="The successfully submitted record is referenced in record mode.")
    def test_connection_error_with_bad_api_base(self, azure_open_ai_connection):
        error_codes = "UserError/OpenAIError/APIConnectionError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            prompty = load_prompty(
                connection=azure_open_ai_connection,
                configuration={"azure_endpoint": "https://gpt-test-eus11.openai.azure.com/"},
            )
            prompty(question="what is the result of 1+1?")
        assert "Connection error." in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skipif(pytest.is_replay, reason="The successfully submitted record is referenced in record mode.")
    def test_not_found_error_with_bad_api_version(self, azure_open_ai_connection):
        """NotFoundError: Resource not found"""
        raw_message = "Resource not found"
        error_codes = "UserError/OpenAIError/NotFoundError"
        # Chat will throw: Exception occurs: NotFoundError: Resource not found
        with pytest.raises(WrappedOpenAIError) as exc_info:
            prompty = load_prompty(connection=azure_open_ai_connection, configuration={"api_version": "2022-12-23"})
            prompty(question="what is the result of 1+1?")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_not_found_error_with_bad_deployment(self, azure_open_ai_connection):
        """
        NotFoundError: The API deployment for this resource does not exist.
        If you created the deployment within the last 5 minutes, please wait a moment and try again.
        """
        # This will throw InvalidRequestError
        raw_message = (
            "The API deployment for this resource does not exist. If you created the deployment "
            "within the last 5 minutes, please wait a moment and try again."
        )
        error_codes = "UserError/OpenAIError/NotFoundError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            prompty = load_prompty(
                connection=azure_open_ai_connection, configuration={"azure_deployment": "mock_deployment"}
            )
            prompty(question="what is the result of 1+1?")
        assert raw_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    def test_rate_limit_error_insufficient_quota(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = RateLimitError(
            "Something went wrong",
            response=httpx.Response(429, request=httpx.Request("GET", "https://www.example.com")),
            body={"type": "insufficient_quota"},
        )
        mock_method = mocker.patch("openai.resources.chat.Completions.create", side_effect=dummyEx)
        error_codes = "UserError/OpenAIError/RateLimitError"
        with pytest.raises(WrappedOpenAIError) as exc_info:
            prompty = load_prompty(connection=azure_open_ai_connection)
            prompty(question="what is the result of 1+1?")
        assert to_openai_error_message(dummyEx) == exc_info.value.message
        assert mock_method.call_count == 1
        assert exc_info.value.error_codes == error_codes.split("/")

    def create_api_connection_error_with_cause():
        error = APIConnectionError(request=httpx.Request("GET", "https://www.example.com"))
        error.__cause__ = Exception("Server disconnected without sending a response.")
        return error

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError(
                        "Something went wrong",
                        response=httpx.Response(429, request=httpx.Request("GET", "https://www.example.com")),
                        body=None,
                    ),
                    APITimeoutError(request=httpx.Request("GET", "https://www.example.com")),
                    APIConnectionError(
                        message="('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))",
                        request=httpx.Request("GET", "https://www.example.com"),
                    ),
                    create_api_connection_error_with_cause(),
                    InternalServerError(
                        "Something went wrong",
                        response=httpx.Response(503, request=httpx.Request("GET", "https://www.example.com")),
                        body=None,
                    ),
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError(
                        "Something went wrong",
                        response=httpx.Response(429, request=httpx.Request("GET", "https://www.example.com")),
                        body=None,
                    ),
                    APITimeoutError(request=httpx.Request("GET", "https://www.example.com")),
                    APIConnectionError(
                        message="('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))",
                        request=httpx.Request("GET", "https://www.example.com"),
                    ),
                    create_api_connection_error_with_cause(),
                    InternalServerError(
                        "Something went wrong",
                        response=httpx.Response(503, request=httpx.Request("GET", "https://www.example.com")),
                        body=None,
                    ),
                ]
            ),
        ],
    )
    async def test_retriable_openai_error_handle_async(self, mocker: MockerFixture, dummyExceptionList):
        for dummyEx in dummyExceptionList:
            # Patch the test_method to throw the desired exception
            patched_test_method = mocker.patch(
                "openai.resources.Completions.create", new_callable=AsyncMock, side_effect=dummyEx
            )

            # Apply the retry decorator to the patched test_method
            max_retry = 2
            decorated_test_method = handle_openai_error_async(tries=max_retry)(patched_test_method)
            mock_sleep = mocker.patch(
                "asyncio.sleep", new_callable=AsyncMock
            )  # Create a separate mock for asyncio.sleep

            with pytest.raises(UserErrorException) as exc_info:
                await decorated_test_method()

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
                    RateLimitError(
                        "Something went wrong",
                        response=httpx.Response(
                            429, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
                        ),
                        body=None,
                    ),
                    InternalServerError(
                        "Something went wrong",
                        response=httpx.Response(
                            503, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
                        ),
                        body=None,
                    ),
                ]
            ),
        ],
    )
    def test_retriable_openai_error_handle_with_header(self, mocker: MockerFixture, dummyExceptionList):
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    RateLimitError(
                        "Something went wrong",
                        response=httpx.Response(
                            429, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
                        ),
                        body=None,
                    ),
                    InternalServerError(
                        "Something went wrong",
                        response=httpx.Response(
                            503, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
                        ),
                        body=None,
                    ),
                ]
            ),
        ],
    )
    async def test_retriable_openai_error_handle_with_header_async(self, mocker, dummyExceptionList):
        for dummyEx in dummyExceptionList:
            # Patch the test_method to throw the desired exception
            patched_test_method = mocker.patch(
                "promptflow.tools.aoai.completion", new_callable=AsyncMock, side_effect=dummyEx
            )

            # Apply the retry decorator to the patched test_method
            max_retry = 2
            header_delay = 0.3
            decorated_test_method = handle_openai_error_async(tries=max_retry)(patched_test_method)
            mock_sleep = mocker.patch(
                "asyncio.sleep", new_callable=AsyncMock
            )  # Create a separate mock for asyncio.sleep

            with pytest.raises(UserErrorException) as exc_info:
                await decorated_test_method()

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
            "Something went wrong",
            response=httpx.Response(422, request=httpx.Request("GET", "https://www.example.com")),
            body=None,
        )
        rate_limit_error = RateLimitError(
            "Something went wrong",
            response=httpx.Response(
                429, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
            ),
            body=None,
        )
        # for below exception sequence, "consecutive_422_error_count" changes: 0 -> 1 -> 0 -> 1 -> 2.
        exception_sequence = [
            unprocessable_entity_error,
            rate_limit_error,
            unprocessable_entity_error,
            unprocessable_entity_error,
        ]
        patched_test_method = mocker.patch("promptflow.tools.aoai.AzureOpenAI.chat", side_effect=exception_sequence)
        # limit api connection error retry threshold to 2.
        decorated_test_method = handle_openai_error(unprocessable_entity_error_tries=2)(patched_test_method)
        with pytest.raises(ExceedMaxRetryTimes):
            decorated_test_method()
        assert patched_test_method.call_count == 4

    @pytest.mark.asyncio
    async def test_unprocessable_entity_error_async(self, mocker):
        unprocessable_entity_error = UnprocessableEntityError(
            "Something went wrong",
            response=httpx.Response(422, request=httpx.Request("GET", "https://www.example.com")),
            body=None,
        )
        rate_limit_error = RateLimitError(
            "Something went wrong",
            response=httpx.Response(
                429, request=httpx.Request("GET", "https://www.example.com"), headers={"retry-after": "0.3"}
            ),
            body=None,
        )
        # for below exception sequence, "consecutive_422_error_count" changes: 0 -> 1 -> 0 -> 1 -> 2.
        exception_sequence = [
            unprocessable_entity_error,
            rate_limit_error,
            unprocessable_entity_error,
            unprocessable_entity_error,
        ]
        patched_test_method = mocker.patch(
            "promptflow.tools.aoai.AzureOpenAI.chat", new_callable=AsyncMock, side_effect=exception_sequence
        )
        # limit api connection error retry threshold to 2.
        decorated_test_method = handle_openai_error_async(unprocessable_entity_error_tries=2)(patched_test_method)

        with pytest.raises(ExceedMaxRetryTimes):
            await decorated_test_method()

        assert patched_test_method.call_count == 4

    @pytest.mark.parametrize(
        "dummyExceptionList",
        [
            (
                [
                    AuthenticationError(
                        "Something went wrong", response=httpx.get("https://www.example.com"), body=None
                    ),
                    BadRequestError("Something went wrong", response=httpx.get("https://www.example.com"), body=None),
                ]
            ),
        ],
    )
    def test_non_retriable_openai_error_handle(
        self, azure_open_ai_connection, mocker: MockerFixture, dummyExceptionList
    ):
        for dummyEx in dummyExceptionList:
            mock_method = mocker.patch("openai.resources.chat.Completions.create", side_effect=dummyEx)
            with pytest.raises(UserErrorException) as exc_info:
                prompty = load_prompty(connection=azure_open_ai_connection)
                prompty(question="what is the result of 1+1?")
            assert to_openai_error_message(dummyEx) == exc_info.value.message
            error_codes = "UserError/OpenAIError/" + type(dummyEx).__name__
            assert exc_info.value.error_codes == error_codes.split("/")
            assert mock_method.call_count == 1

    def test_unexpected_error_handle(self, azure_open_ai_connection, mocker: MockerFixture):
        dummyEx = Exception("Something went wrong")
        mock_method = mocker.patch("openai.resources.chat.Completions.create", side_effect=dummyEx)
        error_codes = "UserError/LLMError"

        with pytest.raises(LLMError) as exc_info:
            prompty = load_prompty(connection=azure_open_ai_connection)
            prompty(question="what is the result of 1+1?")
        assert to_openai_error_message(dummyEx) != exc_info.value.args[0]
        assert "OpenAI API hits exception: Exception: Something went wrong" == exc_info.value.message
        assert mock_method.call_count == 1
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.skipif(condition=not pytest.is_live, reason="OpenAI response failed.")
    @pytest.mark.parametrize(
        "max_tokens, error_message, error_codes, exception",
        [
            (0, "0 is less than the minimum of 1", "UserError/OpenAIError/BadRequestError", WrappedOpenAIError),
            (-1, "-1 is less than the minimum of 1", "UserError/OpenAIError/BadRequestError", WrappedOpenAIError),
            ("invalid_max_token", "not of type 'integer'", "UserError/OpenAIError/BadRequestError", WrappedOpenAIError),
        ],
    )
    def test_invalid_max_tokens(self, azure_open_ai_connection, max_tokens, error_message, error_codes, exception):
        with pytest.raises(exception) as exc_info:
            prompty = load_prompty(
                connection=azure_open_ai_connection, parameters={"max_tokens": max_tokens, "temperature": 0}
            )
            prompty(question="what is the result of 1+1?")
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")
