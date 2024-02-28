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
    # init flow executor and validate flow

    # init line process pool

    # return json response
    pass


@router.post("/execution")
async def execution(request: LineExecutionRequest):
    # get pool

    # submit a run

    # return line result

    pass


@router.post("/aggregation")
async def aggregation(request: AggregationRequest):
    pass
