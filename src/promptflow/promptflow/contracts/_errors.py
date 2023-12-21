from promptflow.exceptions import UserErrorException, ValidationException


class FailedToImportModule(UserErrorException):
    pass


class InvalidImageInput(ValidationException):
    pass


class DuplicateNodeName(ValidationException):
    pass
