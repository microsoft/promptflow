# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uvicorn
from fastapi import FastAPI

from promptflow.executor.service.apis.common import router as common_router

app = FastAPI()
app.include_router(common_router)


if __name__ == "__main__":
    uvicorn.run("promptflow.executor.service.app:app", port=8000)
