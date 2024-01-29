# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.exceptions import UserErrorException, ValidationException


class ValueErrorException(ValidationException, ValueError):
    pass


class NotImplementedErrorException(UserErrorException, NotImplementedError):
    pass


class TypeErrorException(ValidationException, TypeError):
    pass


class FileNotFoundException(ValidationException, FileNotFoundError):
    pass


ValueError = ValueErrorException
NotImplementedError = NotImplementedErrorException
TypeError = TypeErrorException
FileNotFoundError = FileNotFoundException
