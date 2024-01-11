from promptflow.exceptions import UserErrorException, ValidationException


class FailedToImportModule(UserErrorException):
    pass


class FlowDefinitionError(UserErrorException):
    pass

class InvalidSource(ValidationException):
    pass
