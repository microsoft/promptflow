# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
import string
import sys
import traceback
from enum import Enum
from functools import cached_property
from typing import Union

from azure.core.exceptions import HttpResponseError


class ErrorTarget(str, Enum):
    """The target of the error, indicates which part of the system the error occurs."""

    EXECUTOR = "Executor"
    BATCH = "Batch"
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
    FUNCTION_PATH = "FunctionPath"


class PromptflowException(Exception):
    """Base exception for all errors.

    :param message: A message describing the error. This is the error message the user will see.
    :type message: str
    :param target: The name of the element that caused the exception to be thrown.
    :type target: ~promptflow.exceptions.ErrorTarget
    :param error: The original exception if any.
    :type error: Exception
    """

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.UNKNOWN,
        module=None,
        **kwargs,
    ):
        self._inner_exception = kwargs.get("error")
        self._target = target
        self._module = module
        self._message_format = message_format
        self._kwargs = kwargs
        if message:
            self._message = str(message)
        elif self.message_format:
            self._message = self.message_format.format(**self.message_parameters)
        else:
            self._message = self.__class__.__name__
        super().__init__(self._message)

    @property
    def message(self):
        """The error message."""
        return self._message

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
                parameters[argument] = f"<{argument}>"
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
        :rtype: ~promptflow.exceptions.ErrorTarget
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
        # In Python 3.11, the __str__ method of the Enum type returns the name of the enumeration member.
        # However, in earlier Python versions, the __str__ method returns the value of the enumeration member.
        # Therefore, when dealing with this situation, we need to make some additional adjustments.
        target = self.target.value if isinstance(self.target, ErrorTarget) else self.target
        if self.module:
            return f"{target}/{self.module}"
        else:
            return target

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
                if field_name is not None:
                    yield field_name

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


class ErrorCategory:
    HttpResponseError = 'HttpResponseError'
    SDKUserError = 'SDKUserError'  # This error indicates that the user provided parameter doesn't pass validation
    UserError = 'UserErrorException'  # This error indicates that the user's code has errors
    ExecutorError = 'ExecutorError'
    InternalSDKError = 'InternalSDKError'  # This error indicates that our package has some problems

    @classmethod
    def get_error_info(cls, e: Exception):
        if cls._is_user_error_from_exception_type(e) or cls._is_user_error_from_exception_type(e.__cause__):
            return cls.SDKUserError
        if isinstance(e, HttpResponseError):
            return cls.HttpResponseError

        return cls.classify_exception_to_internal_or_external(e)

    @classmethod
    def _is_user_error_from_exception_type(cls, e: Union[Exception, None]):
        """Determine whether if an exception is user error from it's exception type."""
        # Connection error happens on user's network failure, should be user error
        if isinstance(e, ConnectionError):
            return True

        # UserErrorException and KeyboardInterrupt should be sdk user error
        if isinstance(e, (UserErrorException, KeyboardInterrupt)):
            return True

        # For OSError/IOError with error no 28: "No space left on device" should be sdk user error
        if isinstance(e, (IOError, OSError)) and e.errno == 28:
            return True

    @classmethod
    def _is_dsl_pipeline_customer_code_error(cls):
        """Check whether the error is raised by customer code in dsl.pipeline"""
        _, _, exc_traceback = sys.exc_info()
        if exc_traceback is None:
            return False
        # This is the frame where the exception is actually raises
        traceback_frame_list = [frame for frame, _ in traceback.walk_tb(exc_traceback)]
        last_frame = traceback_frame_list[-1]

        # When using exec to execute and globals are not specified, it's not able to identify error category.
        # If using exec to execute and __package__ not exist, it is classified as CustomerUserError.
        is_all_package_exists = next((frame for frame in traceback_frame_list if "__package__" not in frame.f_globals),
                                     None) is None
        if not is_all_package_exists:
            return True

        # We find the last frame which is in SDK code instead of customer code or dependencies code
        # by checking whether the package name of the frame belongs to azure.ml.component.
        pattern = r'(^azure\.ml\.component(?=\..*|$).*)'

        last_frame_in_sdk = next(
            (frame for frame in traceback_frame_list[::-1] if cls._assert_frame_package_name(pattern, frame)), None)
        if not last_frame_in_sdk:
            return False

        # If the last frame which raises exception is in SDK code, it is not customer error.
        if last_frame == last_frame_in_sdk:
            return False
        # If the last frame in SDK is the pipeline decorator, the exception is caused by customer code, return True
        # Otherwise the exception might be some dependency error, return False
        target_mod, target_funcs = 'azure.ml.component._pipeline_component_definition_builder', \
            ['__call__', '_get_func_outputs']
        return last_frame_in_sdk.f_globals[
            '__name__'] == target_mod and last_frame_in_sdk.f_code.co_name in target_funcs

    @classmethod
    def classify_exception_to_internal_or_external(cls, e: Exception):
        """
        If some dependent packages (like azure and azureml) raise exception, it is classified as ExternalSDKError.
        If other packages raise exception, it is classified as InternalSDKError.
        This function will get the exception traceback and check whether the frame belongs to azure or azureml.
        If there is a frame in the traceback belongs to azure or azureml, it will be regarded as ExternalSDKError,
        otherwise it is regarded as InternalSDKError.
        """
        pattern = r'(^azure\.(?!ml\.component(\..*|$)).*|^azureml\..*)'
        _, _, exc_traceback = sys.exc_info()
        for frame, _ in traceback.walk_tb(exc_traceback):
            if cls._assert_frame_package_name(pattern, frame):
                return ErrorCategory.ExternalSDKError
        return ErrorCategory.InternalSDKError

    @classmethod
    def _assert_frame_package_name(cls, pattern, frame):
        """Check the package name of frame is match pattern."""
        # f_globals records the function's module globals of the frame. And __package__ of module must be set.
        # https://docs.python.org/3/reference/import.html#__package__
        # Although __package__ is set when importing, it may happen __package__ does not exist in globals
        # when using exec to execute.
        package_name = frame.f_globals.get('__package__', "")
        return True if package_name and re.match(pattern, package_name) else False
