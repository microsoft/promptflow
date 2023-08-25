from promptflow.exceptions import UserErrorException


class FailedToImportModule(UserErrorException):
    pass


class ConditionConflictError(UserErrorException):
    pass
