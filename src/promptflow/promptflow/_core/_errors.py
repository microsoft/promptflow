from traceback import TracebackException

from promptflow._utils.exception_utils import ADDITIONAL_INFO_USER_EXECUTION_ERROR, last_frame_info
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException


class NotSupportedError(SystemErrorException):
    """Exception raised when the feature is not supported."""

    pass


class PackageToolNotFoundError(ValidationException):
    """Exception raised when package tool is not found in the current runtime environment."""

    pass


class LoadToolError(ValidationException):
    pass


class MissingRequiredInputs(LoadToolError):
    pass


class ToolExecutionError(UserErrorException):
    """Exception raised when tool execution failed."""

    def __init__(self, *, node_name: str, module: str = None):
        self._node_name = node_name
        super().__init__(target=ErrorTarget.TOOL, module=module)

    @property
    def message_format(self):
        if self.inner_exception:
            return "Execution failure in '{node_name}': {error_type_and_message}"
        else:
            return "Execution failure in '{node_name}'."

    @property
    def message_parameters(self):
        error_type_and_message = None
        if self.inner_exception:
            error_type_and_message = f"({self.inner_exception.__class__.__name__}) {self.inner_exception}"

        return {
            "node_name": self._node_name,
            "error_type_and_message": error_type_and_message,
        }

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
            # The first frame is always the code in flow.py who invokes the tool.
            # We do not want to dump it to user code's traceback.
            # So, just skip it by looking up for `tb_next` here.
            tb = exc.__traceback__.tb_next
            if tb is not None:
                # We don't use traceback.format_exception since its interface differs between 3.8 and 3.10.
                # Use this internal class to adapt to different python versions.
                te = TracebackException(type(exc), exc, tb)
                formatted_tb = "".join(te.format())

                # For inline scripts that are not saved into a file,
                # The traceback will show "<string>" as the file name.
                # For these cases, replace with the node name for better understanding.
                #
                # Here is a default traceback for example:
                #   File "<string>", line 1, in <module>
                #
                # It will be updated to something like this:
                #   In "my_node", line 1, in <module>
                if self._node_name:
                    # policy: http://policheck.azurewebsites.net/Pages/TermInfo.aspx?LCID=9&TermID=79670
                    formatted_tb = formatted_tb.replace('File "<string>"', 'In "{}"'.format(self._node_name))

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
