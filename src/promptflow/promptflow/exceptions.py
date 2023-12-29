# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import string
import traceback
from enum import Enum
from functools import cached_property
from azure.core.exceptions import HttpResponseError
from promptflow._utils.utils import get_exception_classes


class ErrorCategory(str, Enum):
    SDKUserError = "SDKUserError"
    SystemError = "SystemError"


class ErrorType(str, Enum):
    ExecutorError = "ExecutorError"
    PFSError = "PFSError"
    CoreError = "CoreError"
    BatchError = "BatchError"
    ContractsError = "ContractsError"
    UtilsError = "UtilsError"
    StorageError = "StorageError"
    SDKError = "SDKError"
    CLIError = "CLIError"
    ExternalSyetemError = "ExternalSyetemError"
    ExternalUserError = "ExternalUserError"


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


class ErrorInfo:
    _serving_error_classes = None
    _sdk_error_classes = None
    _core_error_classes = None
    _utils_error_classes = None
    _batch_error_classes = None
    _contracts_error_classes = None
    _storage_error_classes = None
    _executor_error_classes = None
    _modules = dict()

    @classmethod
    def get_error_info(cls, e: Exception):
        if not isinstance(e, Exception):
            return None, None, None, None

        e = cls.select_exception(e)
        if cls._is_system_error(e):
            return ErrorCategory.SystemError, cls._error_type(e), cls._error_target(e), cls._error_message(e)

        return ErrorCategory.SDKUserError, cls._error_type(e), cls._error_target(e), cls._error_message(e)

    @classmethod
    def select_exception(cls, e: Exception):
        """Select the exception  in e and e.__cause__, and prioritize the Exception defined in the SDK."""

        if e.__cause__ and isinstance(e.__cause__, PromptflowException):
            return e.__cause__

        if isinstance(e, PromptflowException):
            return e

        if e.__cause__ and isinstance(e.__cause__, HttpResponseError):
            return e.__cause__

        return e

    @classmethod
    def _is_system_error(cls, e: Exception):
        if isinstance(e, (SystemErrorException, HttpResponseError)):
            return True
        if hasattr(e, "status_code") or (hasattr(e, "response") and hasattr(e.response, "status_code")):
            status_code = str(e.status_code) if hasattr(e, "status_code") else str(e.response.status_code)
            if not status_code.startswith("40"):
                return True

        return False

    @classmethod
    def _error_type(cls, e: Exception):
        # executor error
        if isinstance(e, cls.executor_error_classes()):
            return ErrorType.ExecutorError
        if cls._is_exception_from_module(e, module_name="promptflow.executor"):
            return ErrorType.ExecutorError

        # pfs error
        if isinstance(e, cls.serving_error_classes()):
            return ErrorType.PFSError
        if cls._is_exception_from_module(e, module_name="promptflow._sdk._serving"):
            return ErrorType.PFSError

        # storage error
        if isinstance(e, cls.storage_error_classes()):
            return ErrorType.StorageError
        if cls._is_exception_from_module(e, module_name="promptflow.storage"):
            return ErrorType.StorageError

        # batch error
        if isinstance(e, cls.batch_error_classes()):
            return ErrorType.BatchError
        if cls._is_exception_from_module(e, module_name="promptflow.batch"):
            return ErrorType.BatchError

        # utils error
        if isinstance(e, cls.utils_error_classes()):
            return ErrorType.UtilsError
        if cls._is_exception_from_module(e, module_name="promptflow._utils"):
            return ErrorType.UtilsError

        # contrasts error
        if isinstance(e, cls.contracts_error_classes()):
            return ErrorType.ContractsError
        if cls._is_exception_from_module(e, module_name="promptflow.contracts"):
            return ErrorType.ContractsError

        # core error
        if isinstance(e, cls.core_error_classes()):
            return ErrorType.CoreError
        if cls._is_exception_from_module(e, module_name="promptflow._core"):
            return ErrorType.CoreError

        # sdk error
        if isinstance(e, cls.sdk_error_classes()):
            return ErrorType.SDKError
        if cls._is_exception_from_module(e, module_name="promptflow._sdk"):
            return ErrorType.SDKError

        # cli error
        if cls._is_exception_from_module(e, module_name="promptflow._cli"):
            return ErrorType.CLIError

        # other error
        if cls._is_system_error(e):
            return ErrorType.ExternalSyetemError

        return ErrorType.ExternalUserError

    @classmethod
    def _error_target(cls, e: Exception):
        return getattr(e, "target", ErrorTarget.UNKNOWN)

    @classmethod
    def _error_message(cls, e: Exception):
        exception_codes = cls._get_exception_codes(e)
        msg = getattr(e, "message_format", "")
        name = type(e).__name__
        exception_code = exception_codes[-1]
        for item in exception_codes[::-1]:  # Prioritize recording the location of promptflow package errors
            if "promptflow" in item["module"]:
                exception_code = item
                break
        return (
            f"exception name={name}, "
            f"exception msg={msg}, "
            f"exception module={exception_code['module']}, "
            f"exception code={exception_code['exception_code']}, "
            f"exception lineno={exception_code['lineno']}"
        )

    @classmethod
    def _get_exception_codes(cls, e: Exception) -> list:
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
        key = str(id(e))
        if cls._modules.get(key):
            return cls._modules[key]

        cls._modules[key] = []  # Considering multithreading, use dict to save.
        traceback_info = traceback.extract_tb(e.__traceback__)
        for item in traceback_info:
            lineno = item.lineno
            filename = item.filename
            exception_code = item.line
            module = inspect.getmodule(None, _filename=filename)
            exception_code = {"module": "", "exception_code": exception_code, "lineno": lineno}
            if module is not None:
                exception_code["module"] = module.__name__
            cls._modules[key].append(exception_code)

        return cls._modules.get(key, [])

    @classmethod
    def _is_exception_from_module(cls, e: Exception, module_name: str = ""):
        exception_codes = cls._get_exception_codes(e)
        for exception_code in exception_codes[::-1]:
            # For example: 'promptflow.executor._errors' in 'promptflow.executor'
            if module_name in exception_code["module"]:
                return True

        return False

    @classmethod
    def executor_error_classes(cls):
        if cls._executor_error_classes is None:
            import promptflow.executor._errors as _errors_module

            cls._executor_error_classes = get_exception_classes(_errors_module)

        return cls._executor_error_classes

    @classmethod
    def storage_error_classes(cls):
        if cls._storage_error_classes is None:
            import promptflow.storage._errors as _errors_module

            cls._storage_error_classes = get_exception_classes(_errors_module)

        return cls._storage_error_classes

    @classmethod
    def contracts_error_classes(cls):
        if cls._contracts_error_classes is None:
            import promptflow.contracts._errors as _errors_module

            cls._contracts_error_classes = get_exception_classes(_errors_module)

        return cls._contracts_error_classes

    @classmethod
    def batch_error_classes(cls):
        if cls._batch_error_classes is None:
            import promptflow.batch._errors as _errors_module

            cls._batch_error_classes = get_exception_classes(_errors_module)

        return cls._batch_error_classes

    @classmethod
    def utils_error_classes(cls):
        if cls._utils_error_classes is None:
            import promptflow._utils._errors as _errors_module

            cls._utils_error_classes = get_exception_classes(_errors_module)

        return cls._utils_error_classes

    @classmethod
    def core_error_classes(cls):
        if cls._core_error_classes is None:
            import promptflow._core._errors as _errors_module

            cls._core_error_classes = get_exception_classes(_errors_module)

        return cls._core_error_classes

    @classmethod
    def serving_error_classes(cls):
        if cls._serving_error_classes is None:
            import promptflow._sdk._serving._errors as _errors_module

            cls._serving_error_classes = get_exception_classes(_errors_module)

        return cls._serving_error_classes

    @classmethod
    def sdk_error_classes(cls):
        if cls._sdk_error_classes is None:
            import promptflow._sdk._errors as _errors_module

            cls._sdk_error_classes = get_exception_classes(_errors_module)

        return cls._sdk_error_classes
