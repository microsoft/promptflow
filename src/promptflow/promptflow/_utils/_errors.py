from promptflow.exceptions import SystemErrorException, UserErrorException, ValidationException


class InvalidImageInput(ValidationException):
    pass


class LoadMultimediaDataError(UserErrorException):
    pass


class YamlParseError(SystemErrorException):
    """Exception raised when yaml parse failed."""

    pass
