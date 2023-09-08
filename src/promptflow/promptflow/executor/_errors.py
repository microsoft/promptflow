# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException


class InvalidCustomLLMTool(ValidationException):
    """Exception raised when package tool definition is wrong."""

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


class InputMappingError(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class NoneInputsMappingIsNotSupported(SystemErrorException):
    pass


class NodeResultCountNotMatch(SystemErrorException):
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


class EmptyOutputReference(InvalidFlowRequest):
    pass


class OutputReferenceNotFound(InvalidFlowRequest):
    pass


class InputReferenceNotFound(InvalidFlowRequest):
    pass


class InputNotFound(InvalidFlowRequest):
    pass


class InvalidAggregationInput(SystemErrorException):
    pass


class InputNotFoundFromAncestorNodeOutput(SystemErrorException):
    pass


class NoNodeExecutedError(SystemErrorException):
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

    pass


class UnsupportedReference(NodeReferenceError):
    pass


class InvalidReferenceProperty(NodeReferenceError):
    pass


class OutputReferenceBypassed(NodeReferenceError):
    pass


class OutputReferenceNotExist(NodeReferenceError):
    pass


class ReferenceNodeBypassed(NodeReferenceError):
    pass


class NodeOutputNotFound(UserErrorException):
    pass


class LineExecutionTimeoutError(UserErrorException):
    """Exception raised when single line execution timeout"""

    def __init__(self, line_number, timeout):
        super().__init__(
            message=f"Line {line_number} execution timeout for exceeding {timeout} seconds", target=ErrorTarget.EXECUTOR
        )
