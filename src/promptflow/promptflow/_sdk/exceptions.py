# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import PromptflowException


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
