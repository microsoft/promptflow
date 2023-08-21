# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, PromptflowException


class RunExistsError(PromptflowException):
    """Exception raised when run already exists."""

    pass


class RunNotFoundError(PromptflowException):
    """Exception raised if run cannot be found."""

    pass


class InvalidRunStatusError(PromptflowException):
    """Exception raised if run status is invalid."""

    pass


class UnsecureConnectionError(PromptflowException):
    """Exception raised if connection is not secure."""

    pass


class DecryptConnectionError(PromptflowException):
    """Exception raised if connection decryption failed."""

    pass


class StoreConnectionEncryptionKeyError(PromptflowException):
    """Exception raised if no keyring backend."""

    pass


class InvalidFlowError(PromptflowException):
    """Exception raised if flow definition is not legal."""

    pass


class ConnectionNotFoundError(PromptflowException):
    """Exception raised if connection is not found."""

    pass


class InvalidRunError(PromptflowException):
    """Exception raised if run name is not legal."""

    pass


class GenerateFlowToolsJsonError(PromptflowException):
    """Exception raised if flow tools json generation failed."""

    pass


class BulkRunException(PromptflowException):
    """Exception raised when bulk run failed."""

    def __init__(self, *, failed_lines: int, total_lines: int, module: str = None, **kwargs):
        self.failed_lines = failed_lines
        self.total_lines = total_lines
        super().__init__(target=ErrorTarget.RUNTIME, module=module, **kwargs)

    def to_dict(self, *, include_debug_info=False):
        result = super().to_dict(include_debug_info=include_debug_info)
        result["failed_lines"] = f"{self.failed_lines}/{self.total_lines}"
        return result
