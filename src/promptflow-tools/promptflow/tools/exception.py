from openai.error import OpenAIError

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, infer_error_code_from_class, \
    RootErrorCode

openai_error_code_ref_message = "Error reference: https://platform.openai.com/docs/guides/error-codes/api-errors"


def to_openai_error_message(e: Exception) -> str:
    ex_type = type(e).__name__
    if str(e) == "<empty message>":
        msg = "The api key is invalid or revoked. " \
              "You can correct or regenerate the api key of your connection."
        return f"OpenAI API hits {ex_type}: {msg}"
    # for models that do not support the `functions` parameter.
    elif "Unrecognized request argument supplied: functions" in str(e):
        msg = "Current model does not support the `functions` parameter. If you are using openai connection, then " \
              "please use gpt-3.5-turbo, gpt-4, gpt-4-32k, gpt-3.5-turbo-0613 or gpt-4-0613. You can refer to " \
              "https://platform.openai.com/docs/guides/gpt/function-calling. If you are using azure openai " \
              "connection, then please first go to your Azure OpenAI resource, deploy model 'gpt-35-turbo' or " \
              "'gpt-4' with version 0613, then go to prompt flow connection page, upgrade connection api version to " \
              "'2023-07-01-preview'. You can refer to " \
              "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling."
        return f"OpenAI API hits {ex_type}: {msg}"
    elif "The completion operation does not work with the specified model" in str(e) or \
            "logprobs, best_of and echo parameters are not available" in str(e):
        msg = "The completion operation does not work with the current model. " \
              "Completion API is a legacy api and is going to be deprecated soon. " \
              "Please change to use Chat API for current model. " \
              "You could refer to guideline at https://aka.ms/pfdoc/chat-prompt " \
              "or view the samples in our gallery that contain 'Chat' in the name."
        return f"OpenAI API hits {ex_type}: {msg}"
    else:
        return f"OpenAI API hits {ex_type}: {str(e)} [{openai_error_code_ref_message}]"


class WrappedOpenAIError(UserErrorException):
    """Base exception raised when call openai api."""

    def __init__(self, ex: OpenAIError, **kwargs):
        super().__init__(target=ErrorTarget.TOOL, **kwargs)
        self._ex = ex

    @property
    def message(self):
        return str(to_openai_error_message(self._ex))

    @property
    def error_codes(self):
        # For openai error, they would be classified as user error. Its error codes would be in below format.
        return [RootErrorCode.USER_ERROR, OpenAIError.__name__, self._ex.__class__.__name__]


class ExceedMaxRetryTimes(WrappedOpenAIError):
    """Base exception raised when retry exceeds max times."""

    @property
    def message(self):
        return "Exceed max retry times. " + super().message


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, target=ErrorTarget.TOOL)


class LLMError(UserErrorException):
    """Base exception raised when failed to call openai api with non-OpenAIError."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, target=ErrorTarget.TOOL)


class JinjaTemplateError(ToolValidationError):
    """Base exception raised when failed to render jinja template."""
    pass


class ChatAPIInvalidRole(ToolValidationError):
    """Base exception raised when failed to validate chat api role."""
    pass


class ChatAPIFunctionRoleInvalidFormat(ToolValidationError):
    """Base exception raised when failed to validate chat api function role format."""
    pass


class ChatAPIInvalidFunctions(ToolValidationError):
    """Base exception raised when failed to validate functions when call chat api."""
    pass


class FunctionCallNotSupportedInStreamMode(ToolValidationError):
    """Base exception raised when use functions parameter in stream mode when call chat api."""

    pass


class InvalidConnectionType(ToolValidationError):
    """Base exception raised when failed to pass invalid connection type."""
    pass


class SerpAPISystemError(SystemErrorException):
    """Base exception raised when failed to call serp api with system error."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, target=ErrorTarget.TOOL)


class SerpAPIUserError(UserErrorException):
    """Base exception raised when failed to call serp api with user error."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs, target=ErrorTarget.TOOL)
