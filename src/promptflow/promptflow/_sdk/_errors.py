# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk._constants import BULK_RUN_LINE_ERRORS
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

    def __init__(self, *, message="", failed_lines: int, total_lines: int, line_errors, module: str = None, **kwargs):
        self.failed_lines = failed_lines
        self.total_lines = total_lines
        self._additional_info = {
            BULK_RUN_LINE_ERRORS: line_errors,
        }

        message = f"Failed to run {failed_lines}/{total_lines} lines: First error message is: {message}"
        super().__init__(message=message, target=ErrorTarget.RUNTIME, module=module, **kwargs)

    @property
    def additional_info(self):
        """Set the tool exception details as additional info."""
        return self._additional_info


class RunOperationParameterError(PromptflowException):
    """Exception raised when list run failed."""

    pass
