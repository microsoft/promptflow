from promptflow.exceptions import UserErrorException


class FailedToImportModule(UserErrorException):
    pass


class FlowDefinitionError(UserErrorException):
    pass
