# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk._constants import BULK_RUN_ERRORS
from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException


class SDKError(UserErrorException):
    """SDK base class, target default is CONTROL_PLANE_SDK."""

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.CONTROL_PLANE_SDK,
        module=None,
        **kwargs,
    ):
        super().__init__(message=message, message_format=message_format, target=target, module=module, **kwargs)


class SDKInternalError(SystemErrorException):
    """SDK internal error."""

    def __init__(
        self,
        message="",
        message_format="",
        target: ErrorTarget = ErrorTarget.CONTROL_PLANE_SDK,
        module=None,
        **kwargs,
    ):
        super().__init__(message=message, message_format=message_format, target=target, module=module, **kwargs)


class RunExistsError(SDKError):
    """Exception raised when run already exists."""

    pass


class RunNotFoundError(SDKError):
    """Exception raised if run cannot be found."""

    pass


class InvalidRunStatusError(SDKError):
    """Exception raised if run status is invalid."""

    pass


class UnsecureConnectionError(SDKError):
    """Exception raised if connection is not secure."""

    pass


class DecryptConnectionError(SDKError):
    """Exception raised if connection decryption failed."""

    pass


class StoreConnectionEncryptionKeyError(SDKError):
    """Exception raised if no keyring backend."""

    pass


class InvalidFlowError(SDKError):
    """Exception raised if flow definition is not legal."""

    pass


class ConnectionNotFoundError(SDKError):
    """Exception raised if connection is not found."""

    pass


class ConnectionNameNotSetError(SDKError):
    """Exception raised if connection not set when create or update."""

    pass


class ConnectionClassNotFoundError(SDKError):
    """Exception raised if relative sdk connection class not found."""

    pass


class InvalidRunError(SDKError):
    """Exception raised if run name is not legal."""

    pass


class GenerateFlowToolsJsonError(SDKError):
    """Exception raised if flow tools json generation failed."""

    pass


class GenerateFlowMetaJsonError(SDKError):
    """Exception raised if flow json generation failed."""

    pass


class BulkRunException(SDKError):
    """Exception raised when bulk run failed."""

    def __init__(self, *, message="", failed_lines, total_lines, errors, module: str = None, **kwargs):
        self.failed_lines = failed_lines
        self.total_lines = total_lines
        self._additional_info = {
            BULK_RUN_ERRORS: errors,
        }

        message = f"First error message is: {message}"
        # bulk run error is line error only when failed_lines > 0
        if isinstance(failed_lines, int) and isinstance(total_lines, int) and failed_lines > 0:
            message = f"Failed to run {failed_lines}/{total_lines} lines. " + message
        super().__init__(message=message, target=ErrorTarget.RUNTIME, module=module, **kwargs)

    @property
    def additional_info(self):
        """Set the tool exception details as additional info."""
        return self._additional_info


class RunOperationParameterError(SDKError):
    """Exception raised when list run failed."""

    pass


class RunOperationError(SDKError):
    """Exception raised when run operation failed."""

    pass


class FlowOperationError(SDKError):
    """Exception raised when flow operation failed."""

    pass


class ExperimentExistsError(SDKError):
    """Exception raised when experiment already exists."""

    pass


class ExperimentNotFoundError(SDKError):
    """Exception raised if experiment cannot be found."""

    pass


class MultipleExperimentTemplateError(SDKError):
    """Exception raised if multiple experiment template yaml found."""

    pass


class NoExperimentTemplateError(SDKError):
    """Exception raised if no experiment template yaml found."""

    pass


class ExperimentValidationError(SDKError):
    """Exception raised if experiment validation failed."""

    pass


class ExperimentValueError(SDKError):
    """Exception raised if experiment validation failed."""

    pass


class ExperimentHasCycle(SDKError):
    """Exception raised if experiment validation failed."""

    pass


class DownloadInternalError(SDKInternalError):
    """Exception raised if download internal error."""

    pass


class UploadInternalError(SDKInternalError):
    """Exception raised if upload internal error."""

    pass


class UploadUserError(SDKError):
    """Exception raised if upload user error."""

    pass


class UserAuthenticationError(SDKError):
    """Exception raised when user authentication failed"""

    pass


class ExperimentNodeRunFailedError(SDKError):
    """Orchestrator raised if node run failed."""

    pass


class ExperimentNodeRunNotFoundError(SDKError):
    """ExpNodeRun raised if node run cannot be found."""

    pass


class ExperimentCommandRunError(SDKError):
    """Exception raised if experiment validation failed."""

    pass


class ChatGroupError(SDKError):
    """Exception raised if chat group operation failed."""

    pass


class ChatRoleError(SDKError):
    """Exception raised if chat agent operation failed."""

    pass


class UnexpectedAttributeError(SDKError):
    """Exception raised if unexpected attribute is found."""

    pass


class LineRunNotFoundError(SDKError):
    """Exception raised if line run cannot be found."""

    pass


class ArtifactInternalError(SDKInternalError):
    """Exception raised if artifact internal error."""

    pass


class AssetInternalError(SDKInternalError):
    """Exception raised if asset internal error."""

    pass


class RunHistoryInternalError(SDKInternalError):
    """Exception raised if run history internal error."""

    pass


class MetricInternalError(SDKInternalError):
    """Exception raised if metric internal error."""

    pass


class MissingAzurePackage(SDKError):
    """Exception raised if missing required package."""

    def __init__(
        self,
        **kwargs,
    ):
        msg = (
            '"promptflow[azure]" is required for this functionality, '
            'please install it by running "pip install promptflow-azure" with your version.'
        )
        super().__init__(message=msg, no_personal_data_message=msg, **kwargs)


class WrongTraceSearchExpressionError(SDKError):
    """Exception raised if the trace search expression is wrong."""

    pass


class PromptFlowServiceInvocationError(SDKError):
    """Exception raised if prompt flow service invocation failed."""

    pass
