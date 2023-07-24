from promptflow.exceptions import ErrorTarget, SystemErrorException, ValidationException


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


class ToolTypeNotSupported(ToolValidationError):
    pass


class ToolLoadError(ToolValidationError):
    pass


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


class RequestTypeNotSupported(InvalidRequest):
    pass


class ConnectionNotFound(InvalidRequest):
    pass


class EmptyInputError(InvalidRequest):
    pass


class EvaluationFlowNotSupported(InvalidRequest):
    pass


class InvalidRunMode(InvalidRequest):
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


class BulkTestIdNotFound(InvalidBulkTestRequest):
    pass


class BaselineVariantIdNotFound(InvalidBulkTestRequest):
    pass


class BaselineVariantInVariants(InvalidBulkTestRequest):
    pass


class EvaluationFlowRunIdNotFound(InvalidBulkTestRequest):
    pass


class VariantCountNotMatchWithRunCount(InvalidBulkTestRequest):
    pass


class InvalidEvalFlowRequest(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class VariantIdNotFound(InvalidEvalFlowRequest):
    pass


class DuplicateVariantId(InvalidEvalFlowRequest):
    pass


class MissingBulkInputs(InvalidEvalFlowRequest):
    pass


class NumberOfInputsAndOutputsNotEqual(InvalidEvalFlowRequest):
    pass


class NoValidOutputLine(InvalidEvalFlowRequest):
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


class NodeOfVariantNotFound(InvalidFlowRequest):
    pass


class ToolOfVariantNotFound(InvalidFlowRequest):
    pass


class InputNotFound(InvalidFlowRequest):
    pass


class InputTypeError(InvalidFlowRequest):
    pass


class InvalidConnectionType(InvalidFlowRequest):
    pass


class NodeReferenceNotFound(InvalidFlowRequest):
    pass


class NodeCircularDependency(InvalidFlowRequest):
    pass


class UnexpectedValueError(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.EXECUTOR, **kwargs)


class ToolNotFoundInFlow(UnexpectedValueError):
    pass
