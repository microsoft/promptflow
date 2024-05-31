# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from openai import OpenAIError

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException

openai_error_code_ref_message = "Error reference: https://platform.openai.com/docs/guides/error-codes/api-errors"


def to_openai_error_message(e: Exception) -> str:
    ex_type = type(e).__name__
    error_message = str(e)
    # https://learn.microsoft.com/en-gb/azure/ai-services/openai/reference
    params_chat_model_cannot_accept = ["best_of", "echo", "logprobs"]
    if error_message == "<empty message>":
        msg = "The api key is invalid or revoked. " "You can correct or regenerate the api key of your connection."
        return f"OpenAI API hits {ex_type}: {msg}"
    # for models that do not support the `functions` parameter.
    elif "Unrecognized request argument supplied: functions" in error_message:
        msg = (
            "Current model does not support the `functions` parameter. If you are using openai connection, then "
            "please use gpt-3.5-turbo, gpt-4, gpt-4-32k, gpt-3.5-turbo-0613 or gpt-4-0613. You can refer to "
            "https://platform.openai.com/docs/guides/gpt/function-calling. If you are using azure openai "
            "connection, then please first go to your Azure OpenAI resource, deploy model 'gpt-35-turbo' or "
            "'gpt-4' with version 0613. You can refer to "
            "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling."
        )
        return f"OpenAI API hits {ex_type}: {msg}"
    elif "The completion operation does not work with the specified model" in error_message or (
        "parameters are not available" in error_message
        and any(param in error_message for param in params_chat_model_cannot_accept)
    ):
        msg = (
            "The completion operation does not work with the current model. "
            "Completion API is a legacy api and is going to be deprecated soon. "
            "Please change to use Chat API for current model."
        )
        return f"OpenAI API hits {ex_type}: {msg}"
    elif "Invalid content type. image_url is only supported by certain models" in error_message:
        msg = (
            "Current model does not support the image input. If you are using openai connection, then please use "
            "gpt-4-vision-preview. You can refer to https://platform.openai.com/docs/guides/vision."
            "If you are using azure openai connection, then please first go to your Azure OpenAI resource, "
            'create a GPT-4 Turbo with Vision deployment by selecting model name: "gpt-4" and '
            'model version "vision-preview". You can refer to '
            "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/gpt-with-vision"
        )
        return f"OpenAI API hits {ex_type}: {msg}"
    elif ("'response_format' of type" in error_message and "is not supported with this model." in error_message) or (
        "Additional properties are not allowed" in error_message and "unexpected) - 'response_format'" in error_message
    ):
        msg = (
            'The response_format parameter needs to be a dictionary such as {"type": "text"}. '
            "The value associated with the type key should be either 'text' or 'json_object' "
            'If you are using openai connection, you can only set response_format to { "type": "json_object" } '
            "when calling gpt-3.5-turbo-1106 or gpt-4-1106-preview to enable JSON mode. You can refer to "
            "https://platform.openai.com/docs/guides/text-generation/json-mode. If you are using azure openai "
            "connection, then please first go to your Azure OpenAI resource, compatible with GPT-4 Turbo and "
            "all GPT-3.5 Turbo models newer than gpt-35-turbo-1106. You can refer to "
            "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/json-mode?tabs=python."
        )
        return f"OpenAI API hits {ex_type}: {msg}"
    elif "Principal does not have access to API/Operation" in error_message:
        msg = (
            "Principal does not have access to API/Operation. If you are using azure openai connection, "
            "please make sure you have proper role assignment on your azure openai resource. You can refer to "
            "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/role-based-access-control"
        )
        return f"OpenAI API hits {ex_type}: {msg}"
    else:
        return f"OpenAI API hits {ex_type}: {error_message} [{openai_error_code_ref_message}]"


class CoreError(UserErrorException):
    """Core base class, target default is CORE."""

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.CORE,
        module=None,
        **kwargs,
    ):
        super().__init__(message=message, message_format=message_format, target=target, module=module, **kwargs)


class CoreInternalError(SystemErrorException):
    """Core internal error."""

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.CORE,
        module=None,
        **kwargs,
    ):
        super().__init__(message=message, message_format=message_format, target=target, module=module, **kwargs)


class GenerateFlowMetaJsonError(CoreError):
    """Exception raised if flow json generation failed."""

    pass


class RequiredEnvironmentVariablesNotSetError(CoreError):
    """Exception raised if connection from_env required env vars not found."""

    def __init__(self, env_vars: list, cls_name: str):
        super().__init__(f"Required environment variables {env_vars} to build {cls_name} not set.")


class OpenURLFailed(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class BuildConnectionError(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class MissingRequiredPackage(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class UserAuthenticationError(UserErrorException):
    """Exception raised when user authentication failed"""

    pass


class InvalidConnectionError(CoreError):
    """Exception raised if provide invalid connection info."""

    pass


class ChatAPIInvalidRoleError(CoreError):
    """Exception raised when failed to validate chat api role."""

    pass


class JinjaTemplateError(CoreError):
    """Base exception raised when failed to render jinja template."""

    pass


class ChatAPIFunctionRoleInvalidFormatError(CoreError):
    """Exception raised when failed to validate chat api function role format."""

    pass


class MissingRequiredInputError(CoreError):
    """Exception raised when missing required input"""

    pass


class InvalidOutputKeyError(CoreError):
    """Exception raised when invalid output key."""

    pass


class InvalidSampleError(CoreError):
    """Exception raise when invalid sample in Prompty."""

    pass


class ChatAPIFunctionRoleInvalidFormat(CoreError):
    """Base exception raised when failed to validate chat api function role format."""

    pass


class ChatAPIToolRoleInvalidFormat(CoreError):
    """Base exception raised when failed to validate chat api tool role format."""

    pass


class ListDeploymentsError(UserErrorException):
    """Exception raise when list deployments."""

    pass


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    pass


class ParseConnectionError(ListDeploymentsError):
    """Exception raise when connection resourceId format invalid."""

    pass


class ChatAPIInvalidFunctions(ToolValidationError):
    """Base exception raised when failed to validate functions when call chat api."""

    pass


class LLMError(UserErrorException):
    """Base exception raised when failed to call openai api with non-OpenAIError."""

    pass


class ChatAPIInvalidTools(ToolValidationError):
    """Base exception raised when failed to validate functions when call chat api."""

    pass


class WrappedOpenAIError(UserErrorException):
    """Refine error messages on top of native openai errors."""

    def __init__(self, ex: OpenAIError, **kwargs):
        self._ex = ex
        super().__init__(**kwargs)

    @property
    def message(self):
        return str(to_openai_error_message(self._ex))

    @property
    def error_codes(self):
        """The hierarchy of the error codes.

        We follow the "Microsoft REST API Guidelines" to define error codes in a hierarchy style.
        See the below link for details:
        https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md#7102-error-condition-responses

        This list will be converted into an error code hierarchy by the prompt flow framework.
        For this case, it will be converted into a data structure that equivalent to:

            {
                "code": "UserError",
                "innerError": {
                    "code": "OpenAIError",
                    "innerError": {
                        "code": self._ex.__class__.__name__,
                        "innerError": None
                    }
                }
            }
        """
        return ["UserError", "OpenAIError", self._ex.__class__.__name__]


class ExceedMaxRetryTimes(WrappedOpenAIError):
    """Base exception raised when retry exceeds max times."""

    @property
    def message(self):
        return "Exceed max retry times. " + super().message


class ConnectionNotFound(CoreError):

    pass


class OpenURLUserAuthenticationError(UserAuthenticationError):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class OpenURLFailedUserError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class OpenURLNotFoundError(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class UnknownConnectionType(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class UnsupportedConnectionAuthType(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class UnsupportedConnectionProviderConfig(UserErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.CORE, **kwargs)


class MalformedConnectionProviderConfig(UserErrorException):
    """Exception raised when connection provider config is malformed."""

    def __init__(self, provider_config, **kwargs):
        message = (
            "Malformed connection provider config, expected azureml://subscriptions/<subscription_id>/"
            "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
            f"workspaces/<workspace_name>, got {provider_config}"
        )
        super().__init__(target=ErrorTarget.CORE, message=message, **kwargs)


class UnsupportedWorkspaceKind(UserErrorException):
    """Exception raised when workspace kind is not supported."""

    def __init__(self, message, **kwargs):
        super().__init__(target=ErrorTarget.CORE, message=message, **kwargs)


class AccessDeniedError(UserErrorException):
    """Exception raised when run info can not be found in storage"""

    def __init__(self, operation: str, target: ErrorTarget):
        super().__init__(message=f"Access is denied to perform operation {operation!r}", target=target)


class AccountNotSetUp(UserErrorException):
    """Exception raised when account is not setup"""

    def __init__(self):
        super().__init__(
            message=(
                "Please run 'az login' or 'az login --use-device-code' to set up account. "
                "See https://docs.microsoft.com/cli/azure/authenticate-azure-cli for more details."
            ),
            target=ErrorTarget.CORE,
        )
