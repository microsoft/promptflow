# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.exceptions import SystemErrorException


class ExecutorServiceUnhealthy(SystemErrorException):
    pass
