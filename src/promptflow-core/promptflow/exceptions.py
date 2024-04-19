# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import string
import traceback
from enum import Enum
from functools import cached_property
from typing import Dict, List


class ErrorCategory(str, Enum):
    USER_ERROR = "UserError"
    SYSTEM_ERROR = "SystemError"
    UNKNOWN = "Unknown"


class ErrorTarget(str, Enum):
    """The target of the error, indicates which part of the system the error occurs."""

    EXECUTOR = "Executor"
    BATCH = "Batch"
    CORE = "Core"
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
    :param privacy_info: To record messages to telemetry, it is necessary to mask private information.
                        If set to None, messages will not be recorded to telemetry.
                        Otherwise, it will replace the content string in messages
                        that contain privacy_info with '{privacy_info}'.
    :type privacy_info: List[str]
    """

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.UNKNOWN,
        module=None,
        privacy_info: List[str] = None,
        **kwargs,
    ):
        self._inner_exception = kwargs.get("error")
        self._target = target
        self._module = module
        self._message_format = message_format
        self._privacy_info = privacy_info
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
        if getattr(self, "_error_codes", None):
            return self._error_codes

        from promptflow._utils.exception_utils import infer_error_code_from_class

        def reversed_error_codes():
            for clz in self.__class__.__mro__:
                if clz is PromptflowException:
                    break
                yield infer_error_code_from_class(clz)

        self._error_codes = list(reversed_error_codes())
        self._error_codes.reverse()
        return self._error_codes

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


class _ErrorInfo:
    @classmethod
    def get_error_info(cls, e: BaseException):
        if not isinstance(e, BaseException):
            return ErrorCategory.UNKNOWN.value, type(e).__name__, ErrorTarget.UNKNOWN.value, "", ""

        if cls._is_user_error(e):
            return (
                ErrorCategory.USER_ERROR.value,
                cls._error_type(e),
                cls._error_target(e).value,
                cls._error_message(e),
                cls._error_detail(e),
            )

        return (
            ErrorCategory.SYSTEM_ERROR.value,
            cls._error_type(e),
            cls._error_target(e).value,
            cls._error_message(e),
            cls._error_detail(e),
        )

    @classmethod
    def _is_system_error(cls, e: BaseException):
        if isinstance(e, SystemErrorException):
            return True
        try:
            from azure.core.exceptions import HttpResponseError
        except ImportError:
            return True
        if isinstance(e, HttpResponseError):
            status_code = str(e.status_code)
            # Except for 429, 400-499 are all client errors.
            if not status_code.startswith("4") and status_code != "429":
                return True

        return False

    @classmethod
    def _is_user_error(cls, e: BaseException):
        if isinstance(e, UserErrorException):
            return True
        if isinstance(e, (KeyboardInterrupt,)):
            return True

        return False

    @classmethod
    def _error_type(cls, e: BaseException):
        """Return exception type.
        Note:
        For PromptflowException(error=ValueError(message="xxx")) or
        UserErrorException(error=ValueError(message="xxx")) or
        SystemErrorException(error=ValueError(message="xxx")),
        the desired return type is ValueError,
        not PromptflowException, UserErrorException and SystemErrorException.
        """

        error_type = type(e).__name__
        if type(e) in (PromptflowException, UserErrorException, SystemErrorException):
            if e.inner_exception:
                error_type = type(e.inner_exception).__name__
        return error_type

    @classmethod
    def _error_target(cls, e: BaseException) -> ErrorTarget:
        error_target = getattr(e, "target", ErrorTarget.UNKNOWN)
        if error_target != ErrorTarget.UNKNOWN and isinstance(error_target, ErrorTarget):
            return error_target

        module_target_map = cls._module_target_map()
        exception_codes = cls._get_exception_codes(e)
        for exception_code in exception_codes[::-1]:
            for module_name, target in module_target_map.items():
                # For example:  "promptflow.executor" in "promptflow.executor._errors"
                if module_name in exception_code["module"]:
                    return target

        return ErrorTarget.EXECUTOR

    @classmethod
    def _module_target_map(cls) -> Dict[str, ErrorTarget]:
        return {
            "promptflow._sdk": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow._cli": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow.azure": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow.connections": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow.entities": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow.operations": ErrorTarget.CONTROL_PLANE_SDK,
            "promptflow.executor": ErrorTarget.EXECUTOR,
            "promptflow._core": ErrorTarget.EXECUTOR,
            "promptflow.batch": ErrorTarget.EXECUTOR,
            "promptflow.contracts": ErrorTarget.EXECUTOR,
            "promptflow._internal": ErrorTarget.EXECUTOR,
            "promptflow.integrations": ErrorTarget.EXECUTOR,
            "promptflow.storage": ErrorTarget.EXECUTOR,
            "promptflow.tools": ErrorTarget.TOOL,
        }

    @classmethod
    def _error_message(cls, e: BaseException):
        privacy_info = e._privacy_info if isinstance(e, PromptflowException) else None
        if privacy_info is None:
            return getattr(e, "message_format", "")
        message = e.message
        for info in privacy_info:
            info = str(info)
            message = message.replace(info, "{privacy_info}")

        return message

    @classmethod
    def _error_detail(cls, e: BaseException):
        promptflow_codes = cls._promptflow_error_traceback(e)
        inner_exception = e.inner_exception if isinstance(e, PromptflowException) else e.__cause__
        if inner_exception:
            promptflow_codes += "The above exception was the direct cause of the following exception:\n"
            promptflow_codes += cls._promptflow_error_traceback(inner_exception)

        return promptflow_codes

    @classmethod
    def _promptflow_error_traceback(cls, e: BaseException):
        exception_codes = cls._get_exception_codes(e)
        promptflow_codes = ""
        for item in exception_codes:
            if "promptflow" in item["module"]:  # Only record the promptflow package and code.
                promptflow_codes += f"{item['module']}, line {item['lineno']}, {item['exception_code']}\n"

        return promptflow_codes

    @classmethod
    def _get_exception_codes(cls, e: BaseException) -> list:
        """
        Obtain information on each line of the traceback, including the module name,
        exception code and lineno where the error occurred.

        :param e: Exception object
        :return: A list, each item contains information for each row of the traceback, which format is like this:
                {
                'module': 'promptflow.executor.errors',
                'exception_code': 'return self.inner_exception.additional_info',
                'lineno': 223
                }
        """
        exception_codes = []
        traceback_info = traceback.extract_tb(e.__traceback__)
        for item in traceback_info:
            lineno = item.lineno
            filename = item.filename
            line_code = item.line
            module = inspect.getmodule(None, _filename=filename)
            exception_code = {"module": "", "exception_code": line_code, "lineno": lineno}
            if module is not None:
                exception_code["module"] = module.__name__
            exception_codes.append(exception_code)

        return exception_codes
