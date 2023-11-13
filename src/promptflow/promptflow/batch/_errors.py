from promptflow.exceptions import ErrorTarget, ValidationException


class InputMappingError(ValidationException):
    def __init__(self, target: ErrorTarget = ErrorTarget.EXECUTOR, **kwargs):
        super().__init__(target=target, **kwargs)
