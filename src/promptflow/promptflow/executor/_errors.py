# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException


class InvalidCustomLLMTool(ValidationException):
    """Exception raised when package tool definition is wrong."""

    pass


class FlowExecutionError(SystemErrorException):
    """Base System Exceptions for flow execution"""

    pass


class ValueTypeUnresolved(ValidationException):
    pass


class ToolValidationError(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class InvalidRequest(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class ConnectionNotFound(InvalidRequest):
    pass


class InvalidBulkTestRequest(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class InputNotFoundInInputsMapping(InvalidBulkTestRequest):
    pass


class InvalidFlowRequest(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class InvalidSource(ValidationException):
    pass


class NodeInputValidationError(InvalidFlowRequest):
    pass


class DuplicateNodeName(InvalidFlowRequest):
    pass


class EmptyOutputError(InvalidFlowRequest):
    pass


class OutputReferenceNotFound(InvalidFlowRequest):
    pass


class InputReferenceNotFound(InvalidFlowRequest):
    pass


class InputNotFound(InvalidFlowRequest):
    pass


class InputNotFoundFromAncestorNodeOutput(FlowExecutionError):
    pass


class InputTypeError(InvalidFlowRequest):
    pass


class InvalidConnectionType(InvalidFlowRequest):
    pass


class NodeReferenceNotFound(InvalidFlowRequest):
    pass


class NodeCircularDependency(InvalidFlowRequest):
    pass


class NodeConcurrencyNotFound(SystemErrorException):
    pass


class NodeReferenceError(UserErrorException):
    """Exception raised when node reference not found or unsupported"""

    def __init__(self, message, target=ErrorTarget.FLOW_EXECUTOR):
        msg = f"Invalid node reference: {message}"
        super().__init__(message=msg, target=target)


class UnsupportedReference(NodeReferenceError):
    pass


class InvalidReferenceProperty(NodeReferenceError):
    pass


class LineExecutionTimeoutError(UserErrorException):
    """Exception raised when single line execution timeout"""

    def __init__(self, line_number, timeout):
        super().__init__(
            message=f"Line {line_number} execution timeout for exceeding {timeout} seconds", target=ErrorTarget.EXECUTOR
        )
