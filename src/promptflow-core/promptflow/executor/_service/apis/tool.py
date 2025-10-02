# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._core.tool_meta_generator import generate_tool_meta_in_subprocess
from promptflow._core.tools_manager import collect_package_tools
from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service.contracts.tool_request import RetrieveToolFuncResultRequest, ToolMetaRequest
from promptflow.executor._service.utils.service_utils import generate_error_response

router = APIRouter(prefix="/tool")

# Collect package tools when executor server starts to avoid loading latency in request.
collect_package_tools()


@router.get("/package_tools")
def list_package_tools():
    return collect_package_tools()


@router.post("/retrieve_tool_func_result")
async def retrieve_tool_func_result(request: RetrieveToolFuncResultRequest):
    raise NotImplementedError("Function deprecated for security reasons. This should not be reachable.")


@router.post("/meta")
def gen_tool_meta(request: ToolMetaRequest):
    tool_dict, exception_dict = generate_tool_meta_in_subprocess(
        request.working_dir, request.tools, service_logger, prevent_terminate_signal_propagation=True
    )
    exception_dict = {
        source: generate_error_response(error_dict).to_dict() for source, error_dict in exception_dict.items()
    }
    return {"tools": tool_dict, "errors": exception_dict}
