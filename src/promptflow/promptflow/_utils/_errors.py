from promptflow.exceptions import SystemErrorException, UserErrorException, ValidationException


class InvalidImageInput(ValidationException):
    pass


class LoadMultimediaDataError(UserErrorException):
    pass


class YamlParseError(SystemErrorException):
    """Exception raised when yaml parse failed."""

    pass


class CalculatingMetricsError(UserErrorException):
    """The exception that is raised when calculating metrics failed."""

    pass
