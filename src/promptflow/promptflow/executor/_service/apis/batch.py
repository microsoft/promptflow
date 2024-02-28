# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow.executor._service.contracts.batch_request import (
    AggregationRequest,
    InitializationRequest,
    LineExecutionRequest,
)
from promptflow.executor._service.utils.service_utils import set_environment_variables

router = APIRouter()


@router.post("/initialization")
async def initialization(request: InitializationRequest):
    # set envs
    set_environment_variables(request.environment_variables)
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
