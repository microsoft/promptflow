# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, UserErrorException, ValidationException


class InputMappingError(ValidationException):
    def __init__(self, target: ErrorTarget = ErrorTarget.EXECUTOR, **kwargs):
        super().__init__(target=target, **kwargs)


class EmptyInputsData(UserErrorException):
    pass


class BatchRunTimeoutError(UserErrorException):
    pass
