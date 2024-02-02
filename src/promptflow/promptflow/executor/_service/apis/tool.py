# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._core.tools_manager import collect_package_tools

router = APIRouter(prefix="/tool")


@router.get("/package_tools")
async def list_package_tools():
    return collect_package_tools()
