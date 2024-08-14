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
    :param no_personal_data_message: The error message without any personal data. This will be pushed to telemetry logs.
    :type no_personal_data_message: str
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
        no_personal_data_message: str,
        *args,
        target: ErrorTarget = ErrorTarget.UNKNOWN,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        blame: ErrorBlame = ErrorBlame.UNKNOWN,
        **kwargs,
    ) -> None:
        self._category = category
        self._target = target
        self._blame = blame
        self._no_personal_data_message = no_personal_data_message
        super().__init__(message, *args, **kwargs)

    @property
    def target(self) -> ErrorTarget:
        """Return the error target.

        :return: The error target.
        :rtype: ~promptflow.evals._exceptions.ErrorTarget
        """
        return self._target

    @target.setter
    def target(self, value: ErrorTarget):
        self._target = value

    @property
    def no_personal_data_message(self) -> str:
        """Return the error message with no personal data.

        :return: No personal data error message.
        :rtype: str
        """
        return self._no_personal_data_message

    @no_personal_data_message.setter
    def no_personal_data_message(self, value: str):
        self._no_personal_data_message = value

    @property
    def category(self) -> ErrorCategory:
        """Return the error category.

        :return: The error category.
        :rtype: ~promptflow.evals._exceptions.ErrorCategory
        """
        return self._category

    @category.setter
    def category(self, value: ErrorCategory):
        self._category = value

    @property
    def blame(self) -> ErrorBlame:
        """Return who is to blame for the error.

        :return: The error blame.
        :rtype: ~promptflow.evals._exceptions.ErrorBlame
        """
        return self._blame

    @blame.setter
    def blame(self, value: ErrorBlame):
        self._blame = value
