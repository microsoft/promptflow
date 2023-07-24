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
