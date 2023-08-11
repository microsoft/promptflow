from openai.error import OpenAIError

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, infer_error_code_from_class

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
        msg = "The completion operation only support some specified models, please choose the model " \
              "text-davinci-001, text-davinci-002, text-davinci-003, text-curie-001, text-babbage-001, " \
              "text-ada-001, code-cushman-001 or code-davinci-002 for completion operation."
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

    def to_dict(self, *, include_debug_info=False):
        """Return a dict representation of the exception.

        This dict specification corresponds to the specification of the Microsoft API Guidelines:
        https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md#7102-error-condition-responses

        Note that this dict representation the "error" field in the response body of the API.
        The whole error response is then populated in another place outside of this class.
        """

        result = {
            "code": infer_error_code_from_class(UserErrorException),
            "message": self.message,
            "messageFormat": "",
            "messageParameters": {},
            "innerError": {
                "code": "OpenAIError",
                "innerError": {
                    "code": self._ex.__class__.__name__,
                    "innerError": None
                }
            },
            "referenceCode": self.reference_code
        }

        if self.additional_info:
            result["additionalInfo"] = [{"type": k, "info": v} for k, v in self.additional_info.items()]

        if include_debug_info:
            result["debugInfo"] = self.debug_info

        return result


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
