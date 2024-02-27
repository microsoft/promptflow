# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow.executor._service.contracts.batch_request import (
    AggregationRequest,
    InitializationRequest,
    LineExecutionRequest,
)

router = APIRouter()


@router.post("/initialization")
async def initialization(request: InitializationRequest):
    pass


@router.post("/execution")
async def execution(request: LineExecutionRequest):
    pass


@router.post("/aggregation")
async def aggregation(request: AggregationRequest):
    pass
