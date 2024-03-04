# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.exceptions import ErrorTarget, UserErrorException


class FlowFilePathInvalid(UserErrorException):
    pass


class ExecutionTimeoutError(UserErrorException):
    """Exception raised when execution timeout"""

    def __init__(self, timeout):
        super().__init__(
            message_format="Execution timeout for exceeding {timeout} seconds",
            timeout=timeout,
            target=ErrorTarget.EXECUTOR,
        )
