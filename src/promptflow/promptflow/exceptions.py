# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import string
from enum import Enum
from functools import cached_property


class ErrorTarget(str, Enum):
    """The target of the error, indicates which part of the system the error occurs."""

    EXECUTOR = "Executor"
    FLOW_EXECUTOR = "FlowExecutor"
    NODE_EXECUTOR = "NodeExecutor"
    TOOL = "Tool"
    AZURE_RUN_STORAGE = "AzureRunStorage"
    RUNTIME = "Runtime"
    UNKNOWN = "Unknown"
    RUN_TRACKER = "RunTracker"
    RUN_STORAGE = "RunStorage"
    CONTROL_PLANE_SDK = "ControlPlaneSDK"
    SERVING_APP = "ServingApp"
    FLOW_INVOKER = "FlowInvoker"


class PromptflowException(Exception):
    """Base exception for all errors.

    :param message: A message describing the error. This is the error message the user will see.
    :type message: str
    :param target: The name of the element that caused the exception to be thrown.
    :type target: ErrorTarget
    :param error: The original exception if any.
    :type error: Exception
    """

    def __init__(
        self,
        # We must keep the message as the first argument,
        # since some places are using it as positional argument for now.
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.UNKNOWN,
        module=None,
        **kwargs,
    ):
        self._inner_exception = kwargs.get("error")
        self._message = str(message)
        self._target = target
        self._module = module
        self._message_format = message_format
        self._kwargs = kwargs
        super().__init__(self._message)

    @property
    def message(self):
        """The error message."""
        if self._message:
            return self._message

        if self.message_format:
            return self.message_format.format(**self.message_parameters)

        return self.__class__.__name__

    @property
    def message_format(self):
        """The error message format."""
        return self._message_format

    @cached_property
    def message_parameters(self):
        """The error message parameters."""
        if not self._kwargs:
            return {}

        required_arguments = self.get_arguments_from_message_format(self.message_format)
        parameters = {}
        for argument in required_arguments:
            if argument not in self._kwargs:
                # Set one default value for the missing argument to avoid KeyError.
                # For long term solution, use CI to guarantee the message_format and message_parameters are in sync.
                parameters[argument] = "N/A"
            else:
                parameters[argument] = self._kwargs[argument]
        return parameters

    @cached_property
    def serializable_message_parameters(self):
        """The serializable error message parameters."""
        return {k: str(v) for k, v in self.message_parameters.items()}

    @property
    def target(self):
        """The error target.

        :return: The error target.
        :rtype: ErrorTarget
        """
        return self._target

    @target.setter
    def target(self, value):
        """Set the error target."""
        self._target = value

    @property
    def module(self):
        """The module of the error that occurs.

        It is similar to `target` but is more specific.
        It is meant to store the Python module name of the code that raises the exception.
        """
        return self._module

    @module.setter
    def module(self, value):
        """Set the module of the error that occurs."""
        self._module = value

    @property
    def reference_code(self):
        """The reference code of the error."""
        if self.module:
            return f"{self.target}/{self.module}"
        else:
            return self.target

    @property
    def inner_exception(self):
        """Get the inner exception.

        The inner exception can be set via either style:

        1) Set via the error parameter in the constructor.
            raise PromptflowException("message", error=inner_exception)

        2) Set via raise from statement.
            raise PromptflowException("message") from inner_exception
        """
        return self._inner_exception or self.__cause__

    @property
    def additional_info(self):
        """Return a dict of the additional info of the exception.

        By default, this information could usually be empty.

        However, we can still define additional info for some specific exception.
        i.e. For ToolExcutionError, we may add the tool's line number, stacktrace to the additional info.
        """
        return None

    @property
    def error_codes(self):
        """Returns a list of the error codes for this exception.

        The error codes is defined the same as the class inheritance.
        i.e. For ToolExcutionError which inherits from UserErrorException,
        The result would be ["UserErrorException", "ToolExecutionError"].
        """
        from promptflow._utils.exception_utils import infer_error_code_from_class

        def reversed_error_codes():
            for clz in self.__class__.__mro__:
                if clz is PromptflowException:
                    break
                yield infer_error_code_from_class(clz)

        result = list(reversed_error_codes())
        result.reverse()
        return result

    def get_arguments_from_message_format(self, message_format):
        """Get the arguments from the message format."""

        def iter_field_name():
            if not message_format:
                return

            for _, field_name, _, _ in string.Formatter().parse(message_format):
                yield field_name

        # Use set to remove duplicates
        return set(iter_field_name())

    def __str__(self):
        """Return the error message.

        Some child classes may override this method to return a more detailed error message."""
        return self.message


class UserErrorException(PromptflowException):
    """Exception raised when invalid or unsupported inputs are provided."""

    pass


class SystemErrorException(PromptflowException):
    """Exception raised when service error is triggered."""

    pass


class ValidationException(UserErrorException):
    """Exception raised when validation fails."""

    pass
