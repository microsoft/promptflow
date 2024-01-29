# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from promptflow._utils.service_utils import generate_error_response
from promptflow.executor.service.apis.common import router as common_router
from promptflow.executor.service.apis.execution import router as execution_router

app = FastAPI()
app.include_router(common_router)
app.include_router(execution_router)


@app.exception_handler(Exception)
async def exception_handler(ex):
    resp = generate_error_response(ex)
    return JSONResponse(status_code=resp.to_dict(), content=resp.response_code)


if __name__ == "__main__":
    uvicorn.run("promptflow.executor.service.app:app", port=8000, reload=True)
