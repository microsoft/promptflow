# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
from typing import Any, Mapping

from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import LogContext, service_logger
from promptflow._version import VERSION
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest


def get_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    return LogContext(file_path=request.log_path, run_mode=run_mode, credential_list=credential_list)


def get_service_log_context(request: BaseExecutionRequest):
    run_mode = request.get_run_mode()
    return LogContext(file_path=request.log_path, run_mode=run_mode, input_logger=service_logger)


def update_and_get_operation_context(context_dict: Mapping[str, Any]) -> OperationContext:
    operation_context = OperationContext.get_instance()
    if not context_dict:
        return operation_context
    # update operation context with context_dict
    operation_context.update(context_dict)
    # update user agent to operation context
    executor_user_agent = get_executor_version()
    operation_context.append_user_agent(executor_user_agent)
    return operation_context


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
        error_dict = ExceptionPresenter.create(ex).to_dict()
    return ErrorResponse.from_error_dict(error_dict)


def set_environment_variables(envs: Mapping[str, Any]):
    if isinstance(envs, dict) and envs:
        os.environ.update(envs)
