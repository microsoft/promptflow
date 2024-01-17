# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

router = APIRouter()


@router.get("/execution/flow")
async def flow_test(flow):
    pass
