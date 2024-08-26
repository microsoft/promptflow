# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
"""This includes enums and classes for exceptions for use in promptflow-evals."""

from enum import Enum

from azure.core.exceptions import AzureError


class ErrorCategory(Enum):
    """Error category to be specified when using PromptflowEvalsException class.

    When using PromptflowEvalsException, specify the type that best describes the nature of the error being captured.

    * INVALID_VALUE -> One or more inputs are invalid (e.g. incorrect type or format)
    * UNKNOWN_FIELD -> A least one unrecognized parameter is specified
    * MISSING_FIELD -> At least one required parameter is missing
    * FILE_OR_FOLDER_NOT_FOUND -> One or more files or folder paths do not exist
    * RESOURCE_NOT_FOUND -> Resource could not be found
    * FAILED_EXECUTION -> Execution failed
    * UNKNOWN -> Undefined placeholder. Avoid using.
    """

    INVALID_VALUE = "INVALID VALUE"
    UNKNOWN_FIELD = "UNKNOWN FIELD"
    MISSING_FIELD = "MISSING FIELD"
    FILE_OR_FOLDER_NOT_FOUND = "FILE OR FOLDER NOT FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE NOT FOUND"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    UNKNOWN = "UNKNOWN"


class ErrorBlame(Enum):
    """Source of blame to be specified when using PromptflowEvalsException class.

    When using PromptflowEvalsException, specify whether the error is due to user actions or the system.
    """

    USER_ERROR = "UserError"
    SYSTEM_ERROR = "SystemError"
    UNKNOWN = "Unknown"


class ErrorTarget(Enum):
    """Error target to be specified when using PromptflowEvalsException class.

    When using PromptflowEvalsException, specify the code are that was being targeted when the
    exception was triggered.
    """

    UNKNOWN = "Unknown"


class PromptflowEvalsException(AzureError):
    """The base class for all exceptions raised in promptflow-evals. If there is a need to define a custom
    exception type, that custom exception type should extend from this class.

    :param message: A message describing the error. This is the error message the user will see.
    :type message: str
    :param internal_message: The error message without any personal data. This will be pushed to telemetry logs.
    :type internal_message: str
    :param target: The name of the element that caused the exception to be thrown.
    :type target: ~promptflow.evals._exceptions.ErrorTarget
    :param error_category: The error category, defaults to Unknown.
    :type error_category: ~promptflow.evals._exceptionsErrorCategory
    :param error: The original exception if any.
    :type error: Exception
    """

    def __init__(
        self,
        message: str,
        internal_message: str,
        *args,
        target: ErrorTarget = ErrorTarget.UNKNOWN,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        blame: ErrorBlame = ErrorBlame.UNKNOWN,
        **kwargs,
    ) -> None:
        self.category = category
        self.target = target
        self.blame = blame
        self.internal_message = internal_message
        super().__init__(message, *args, **kwargs)
