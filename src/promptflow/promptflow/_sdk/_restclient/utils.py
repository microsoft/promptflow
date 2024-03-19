# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import wraps
from http import HTTPStatus

from promptflow._sdk._restclient.pfs_client.types import Response
from promptflow.exceptions import SystemErrorException


class PFSRequestException(SystemErrorException):
    """PFSRequestException."""

    def __init__(self, message, **kwargs):
        super().__init__(message, **kwargs)


def _request_wrapper():
    """Wrapper for request. Will refresh request id and pretty print exception."""

    def exception_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                raise SystemErrorException(f"Calling {func.__name__} failed with exception: {e} \n")
            if isinstance(result, Response) and result.status_code not in [HTTPStatus.OK]:
                raise PFSRequestException(
                    f"Calling {func.__name__} failed \n"
                    f"Status code: {result.status_code} \n"
                    f"Error message: {result.content.decode('utf-8') } \n"
                )
            return result

        return wrapper

    return exception_wrapper
