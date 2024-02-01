# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os

from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import LogContext, logger, service_logger
from promptflow._version import VERSION
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest


def get_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    return LogContext(file_path=request.log_path, run_mode=run_mode, credential_list=credential_list)


def get_service_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    return LogContext(file_path=request.log_path, run_mode=run_mode, input_logger=service_logger)


def update_operation_context(headers: dict):
    operation_context = OperationContext.get_instance()
    # update user agent to operation context
    operation_context.user_agent = headers.get("context-user-agent", "")
    executor_user_agent = get_executor_version()
    operation_context.append_user_agent(executor_user_agent)
    # update request id to operation context
    request_id = headers.get("context-request-id", "")
    operation_context.request_id = request_id


def get_executor_version():
    build_info = os.environ.get("BUILD_INFO", "")
    try:
        build_info_dict = json.loads(build_info)
        return "promptflow-executor/" + build_info_dict["build_number"]
    except Exception:
        return "promptflow-executor/" + VERSION


def generate_error_response(ex):
    if isinstance(ex, JsonSerializedPromptflowException):
        error_dict = json.loads(ex.message)
    else:
        error_dict = ExceptionPresenter.create(ex).to_dict(include_debug_info=True)
    logger.error(f"Failed to execute the flow: \n{ex}")
    return ErrorResponse.from_error_dict(error_dict)
