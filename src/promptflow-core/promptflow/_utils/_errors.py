from promptflow.exceptions import ErrorTarget, SystemErrorException, UserErrorException, ValidationException


class InvalidImageInput(ValidationException):
    pass


class LoadMultimediaDataError(UserErrorException):
    pass


class YamlParseError(SystemErrorException):
    """Exception raised when yaml parse failed."""

    pass


class ApplyInputMappingError(ValidationException):
    def __init__(self, target: ErrorTarget = ErrorTarget.CORE, **kwargs):
        super().__init__(target=target, **kwargs)


class InvalidMessageFormatType(UserErrorException):
    """Exception raised when the message format from yaml is invalid."""

    pass
