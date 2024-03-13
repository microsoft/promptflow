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
