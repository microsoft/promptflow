# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os

from promptflow._core.connection_manager import ConnectionManager
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import LogContext, logger
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest


def get_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    return LogContext(file_path=request.log_path, run_mode=run_mode, credential_list=credential_list)


def generate_error_response(ex):
    if isinstance(ex, JsonSerializedPromptflowException):
        error_dict = json.loads(ex.message)
    else:
        error_dict = ExceptionPresenter.create(ex).to_dict(include_debug_info=True)
    logger.error(f"Failed to execute the flow: \n{ex}")
    return ErrorResponse.from_error_dict(error_dict)


def set_environment_variables(request: BaseExecutionRequest):
    if isinstance(request.environment_variables, dict) and request.environment_variables:
        os.environ.update(request.environment_variables)
