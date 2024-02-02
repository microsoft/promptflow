# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

router = APIRouter()


@router.get("/tool/package_tools")
async def package_tools():
    return {"message": "This is the tool package"}
