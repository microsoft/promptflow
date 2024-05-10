# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException


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


class ToolValidationError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    pass


class ChatAPIInvalidFunctions(ToolValidationError):
    """Base exception raised when failed to validate functions when call chat api."""

    pass


class ChatAPIInvalidTools(ToolValidationError):
    """Base exception raised when failed to validate functions when call chat api."""

    pass


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
