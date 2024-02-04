# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._core._errors import NoToolTypeDefined
from promptflow._core.tool_meta_generator import generate_tool_meta_dict_by_file
from promptflow._core.tools_manager import collect_package_tools
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow.contracts.tool import ToolType
from promptflow.executor._service._errors import GenerateMetaTimeout
from promptflow.executor._service.contracts.tool_request import ToolMetaRequest
from promptflow.executor._service.utils.process_utils import invoke_function_in_process
from promptflow.executor._service.utils.service_utils import generate_error_response

router = APIRouter(prefix="/tool")


@router.get("/package_tools")
async def list_package_tools():
    return collect_package_tools()


@router.post("/meta")
async def gen_tool_meta(request: ToolMetaRequest):
    result = await invoke_function_in_process(request, {}, gen_meta)
    # For not processed tools, treat as timeout error.
    tool_dict = result["tools"]
    error_dict = result["errors"]
    for source in request.tools.keys():
        if source not in tool_dict and source not in error_dict:
            error_dict[source] = generate_error_response(GenerateMetaTimeout(source)).to_dict()
    return result


async def gen_meta(request: ToolMetaRequest):
    with _change_working_dir(request.working_dir), inject_sys_path(request.working_dir):
        tool_dict = {}
        error_dict = {}
        for source, config in request.tools.items():
            try:
                if "tool_type" not in config:
                    raise NoToolTypeDefined(
                        message_format="Tool type not defined for source '{source}'.",
                        source=source,
                    )
                tool_type = ToolType(config.get("tool_type"))
                tool_dict[source] = generate_tool_meta_dict_by_file(source, tool_type)
            except Exception as e:
                error_dict[source] = generate_error_response(e).to_dict()
        return {"tools": tool_dict, "errors": error_dict}
