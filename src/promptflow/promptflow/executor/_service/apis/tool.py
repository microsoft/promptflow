# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import multiprocessing
import os

from fastapi import APIRouter

from promptflow._core.tool_meta_generator import generate_tool_meta
from promptflow._core.tools_manager import collect_package_tools
from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service._errors import GenerateMetaTimeout
from promptflow.executor._service.contracts.tool_request import RetrieveToolFuncResultRequest, ToolMetaRequest
from promptflow.executor._service.utils.process_utils import SHORT_WAIT_TIMEOUT, invoke_sync_function_in_process
from promptflow.executor._service.utils.service_utils import generate_error_response

router = APIRouter(prefix="/tool")


@router.get("/package_tools")
def list_package_tools():
    return collect_package_tools()


@router.post("/retrieve_tool_func_result")
async def retrieve_tool_func_result(request: RetrieveToolFuncResultRequest):
    from promptflow._core.tools_manager import retrieve_tool_func_result

    args = (request.func_call_scenario, request.func_path, request.func_kwargs, request.ws_triple)
    return await invoke_sync_function_in_process(retrieve_tool_func_result, args=args, wait_timeout=SHORT_WAIT_TIMEOUT)


@router.post("/meta")
def gen_tool_meta(request: ToolMetaRequest):
    manager = multiprocessing.Manager()
    tool_dict = manager.dict()
    exception_dict = manager.dict()
    p = multiprocessing.Process(
        target=generate_tool_meta, args=(request.working_dir, request.tools, tool_dict, exception_dict)
    )
    p.start()
    service_logger.info(f"[{os.getpid()}--{p.pid}] Start process to generate tool meta.")

    p.join(timeout=SHORT_WAIT_TIMEOUT)

    if p.is_alive():
        service_logger.warning(f"Generate meta timeout after {SHORT_WAIT_TIMEOUT} seconds, terminate the process.")
        p.terminate()
        p.join()

    # These dict was created by manager.dict(), so convert to normal dict here.
    resp_tools = {source: tool for source, tool in tool_dict.items()}
    resp_errors = {source: generate_error_response(exception).to_dict() for source, exception in exception_dict.items()}

    # For not processed tools, treat as timeout error.
    for source in request.tools.keys():
        if source not in resp_tools and source not in resp_errors:
            resp_errors[source] = generate_error_response(GenerateMetaTimeout(source)).to_dict()
    return {"tools": resp_tools, "errors": resp_errors}
