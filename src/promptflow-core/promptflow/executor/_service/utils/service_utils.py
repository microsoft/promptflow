# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
from typing import Any, Mapping, Union

from promptflow._core.connection_manager import ConnectionManager
from promptflow._utils.exception_utils import ErrorResponse, ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import LogContext, service_logger
from promptflow._utils.user_agent_utils import append_promptflow_package_ua
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest
from promptflow.tracing._operation_context import OperationContext


def get_log_context(request: BaseExecutionRequest, enable_service_logger: bool = False) -> LogContext:
    run_mode = request.get_run_mode()
    credential_list = ConnectionManager(request.connections).get_secret_list()
    log_context = LogContext(
        file_path=request.log_path,
        run_mode=run_mode,
        credential_list=credential_list,
        flow_logs_folder=request.flow_logs_folder,
    )
    if enable_service_logger:
        log_context.input_logger = service_logger
    return log_context


def update_and_get_operation_context(context_dict: Mapping[str, Any]) -> OperationContext:
    operation_context = OperationContext.get_instance()
    if not context_dict:
        return operation_context
    # update operation context with context_dict
    operation_context.update(context_dict)
    # update promptflow version to operation context
    append_promptflow_package_ua(operation_context)
    return operation_context


def get_commit_id():
    """Get commit id from BUILD_INFO environment variable.

    BUILD_INFO is a json string in the promptflow-python image, like
    '{
        "build_number": "20240326.v2",
        "date": "2024-03-27 05:12:33",
        "commit_id": "...",
        "branch": "main"
    }'
    """
    build_info = os.environ.get("BUILD_INFO", "")
    try:
        build_info_dict = json.loads(build_info)
        return build_info_dict["commit_id"]
    except Exception:
        return "unknown"


def generate_error_response(ex: Union[dict, Exception]):
    if isinstance(ex, dict):
        error_dict = ex
    elif isinstance(ex, JsonSerializedPromptflowException):
        error_dict = json.loads(ex.message)
    else:
        error_dict = ExceptionPresenter.create(ex).to_dict()
    return ErrorResponse.from_error_dict(error_dict)


def set_environment_variables(environment_variables: Mapping[str, Any]):
    if isinstance(environment_variables, dict) and environment_variables:
        os.environ.update(environment_variables)


def enable_async_execution():
    """Set env PF_USE_ASYNC to true to enable async execution"""
    # TODO: Will remove when AsyncNodesScheduler is used by default
    os.environ["PF_USE_ASYNC"] = "true"
