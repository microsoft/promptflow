# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.exceptions import UserErrorException, SystemErrorException, ValidationException


class ValueErrorException(ValidationException, ValueError):
    pass


class NotImplementedErrorException(SystemErrorException, NotImplementedError):
    pass


class TypeErrorException(ValidationException, TypeError):
    pass


class FileNotFoundException(ValidationException, FileNotFoundError):
    pass


class KeyErrorException(UserErrorException, KeyError):
    pass


class RuntimeErrorException(UserErrorException, RuntimeError):
    pass
