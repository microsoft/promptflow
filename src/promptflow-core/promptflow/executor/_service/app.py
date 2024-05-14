# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import typing

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from promptflow._constants import DEFAULT_ENCODING
from promptflow.executor._service.apis.batch import router as batch_router
from promptflow.executor._service.apis.common import router as common_router
from promptflow.executor._service.apis.execution import router as execution_router
from promptflow.executor._service.apis.tool import router as tool_router
from promptflow.executor._service.utils.service_utils import generate_error_response


# Custom JSON response class to allow nan in response.
class CustomJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=True,
            indent=None,
            separators=(",", ":"),
        ).encode(DEFAULT_ENCODING)


app = FastAPI(default_response_class=CustomJSONResponse)

# Register routers
app.include_router(common_router)
app.include_router(execution_router)
app.include_router(tool_router)
app.include_router(batch_router)


@app.exception_handler(Exception)
async def exception_handler(request, exc):
    resp = generate_error_response(exc)
    return JSONResponse(status_code=int(resp.response_code), content=resp.to_dict())
