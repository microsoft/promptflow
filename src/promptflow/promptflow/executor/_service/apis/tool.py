# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._core.tools_manager import collect_package_tools
from promptflow.executor._service.contracts.tool_request import ToolMetaRequest

router = APIRouter(prefix="/tool")


@router.get("/package_tools")
async def list_package_tools():
    return collect_package_tools()


@router.post("/meta")
async def gen_tool_meta(request: ToolMetaRequest):
    return {"status": "healthy", "meta": "meta_dict"}
