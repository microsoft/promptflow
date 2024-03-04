# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from promptflow.executor._service.apis.batch import router as batch_router
from promptflow.executor._service.apis.common import router as common_router
from promptflow.executor._service.apis.execution import router as execution_router
from promptflow.executor._service.apis.tool import router as tool_router
from promptflow.executor._service.utils.service_utils import generate_error_response


class Mode:
    """The mode of the executor service

    normal mode: The main scenarios are flow test, single node run, tools and other functional APIs
    batch mode: Mainly prepared for the batch run
    """

    NORMAL = "normal"
    BATCH = "batch"


app = FastAPI()

app.include_router(common_router)
app.include_router(execution_router)
app.include_router(tool_router)
app.include_router(batch_router)


@app.exception_handler(Exception)
async def exception_handler(request, exc):
    resp = generate_error_response(exc)
    return JSONResponse(status_code=int(resp.response_code), content=resp.to_dict())
