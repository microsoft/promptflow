# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow._core.connection_manager import ConnectionManager
from promptflow._utils.logger_utils import LogContext
from promptflow.executor.service.contracts.execution_request import BaseExecutionRequest


def get_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    return LogContext(file_path=request.log_path, run_mode=run_mode, credential_list=credential_list)
