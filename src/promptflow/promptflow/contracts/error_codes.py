from promptflow.exceptions import ErrorTarget, SystemErrorException

# region contracts.runtime


class FlowRequestDeserializeError(SystemErrorException):
    def __init__(self, **kwargs):
        super().__init__(target=ErrorTarget.RUNTIME, **kwargs)


class InvalidFlowSourceType(FlowRequestDeserializeError):
    pass


class SubmissionDataDeserializeError(FlowRequestDeserializeError):
    pass


class MissingEvalFlowId(FlowRequestDeserializeError):
    pass


class InvalidRunMode(FlowRequestDeserializeError):
    pass


class InvalidValueType(FlowRequestDeserializeError):
    """Exception raised when an unsupported value type is encountered."""

    pass


class InvalidAzureStorageMode(FlowRequestDeserializeError):
    """Exception raised when an unsupported Azure storage mode is encountered."""

    pass


# endregion
