from traceback import TracebackException

from promptflow._utils.exception_utils import (
    ADDITIONAL_INFO_USER_EXECUTION_ERROR,
    is_pf_core_frame,
    last_frame_info,
    remove_suffix,
)
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException


class UnexpectedError(SystemErrorException):
    """Exception raised for unexpected errors that should not occur under normal circumstances."""

    pass


class NotSupported(UserErrorException):
    """This exception should be raised when a feature is not supported by the package or product.
    Customers should take action, such as upgrading the package or using the product in the correct way, to resolve it.
    """

    pass


class PackageToolNotFoundError(ValidationException):
    """Exception raised when package tool is not found in the current runtime environment."""

    pass


class MissingRequiredInputs(ValidationException):
    pass


class InputTypeMismatch(ValidationException):
    pass


class ToolCanceledError(UserErrorException):
    """Exception raised when tool execution is canceled."""

    pass


class InvalidSource(ValidationException):
    pass


class ToolLoadError(UserErrorException):
    """Exception raised when tool load failed."""

    def __init__(self, module: str = None, **kwargs):
        super().__init__(target=ErrorTarget.TOOL, module=module, **kwargs)


class ToolExecutionError(UserErrorException):
    """Exception raised when tool execution failed."""

    def __init__(self, *, node_name: str, module: str = None):
        self._node_name = node_name
        super().__init__(target=ErrorTarget.TOOL, module=module)

    @property
    def message(self):
        if self.inner_exception:
            error_type_and_message = f"({self.inner_exception.__class__.__name__}) {self.inner_exception}"
            return remove_suffix(self._message, ".") + f": {error_type_and_message}"
        else:
            return self._message

    @property
    def message_format(self):
        return "Execution failure in '{node_name}'."

    @property
    def message_parameters(self):
        return {"node_name": self._node_name}

    @property
    def tool_last_frame_info(self):
        """Return the line number inside the tool where the error occurred."""
        return last_frame_info(self.inner_exception)

    @property
    def tool_traceback(self):
        """Return the traceback inside the tool's source code scope.

        The traceback inside the promptflow's internal code will be taken off.
        """
        exc = self.inner_exception
        if exc and exc.__traceback__ is not None:
            tb = exc.__traceback__.tb_next
            if tb is not None:
                # The first frames are always our code invoking the tool.
                # We do not want to dump it to user code's traceback.
                # So, skip these frames from pf core module.
                while is_pf_core_frame(tb.tb_frame) and tb.tb_next is not None:
                    tb = tb.tb_next
                # We don't use traceback.format_exception since its interface differs between 3.8 and 3.10.
                # Use this internal class to adapt to different python versions.
                te = TracebackException(type(exc), exc, tb)
                formatted_tb = "".join(te.format())
                return formatted_tb

        return None

    @property
    def additional_info(self):
        """Set the tool exception details as additional info."""
        if not self.inner_exception:
            # Only populate additional info when inner exception is present.
            return None

        info = {
            "type": self.inner_exception.__class__.__name__,
            "message": str(self.inner_exception),
            "traceback": self.tool_traceback,
        }
        info.update(self.tool_last_frame_info)

        return {
            ADDITIONAL_INFO_USER_EXECUTION_ERROR: info,
        }


class GenerateMetaUserError(UserErrorException):
    """Base exception raised when failed to validate tool."""

    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.EXECUTOR, **kwargs)


class MetaFileNotFound(GenerateMetaUserError):
    pass


class MetaFileReadError(GenerateMetaUserError):
    pass


class RunRecordNotFound(SystemErrorException):
    pass


class FlowOutputUnserializable(UserErrorException):
    pass


class ProcessPoolError(SystemErrorException):
    pass


class DuplicateToolMappingError(ValidationException):
    """Exception raised when multiple tools are linked to the same deprecated tool id."""

    pass
