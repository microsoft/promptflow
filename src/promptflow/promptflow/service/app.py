import uvicorn
from fastapi import FastAPI

from promptflow._utils.service_utils import find_available_port
from promptflow.service.apis.execution import router as execution_router

app = FastAPI()
app.include_router(execution_router)


if __name__ == "__main__":
    port = find_available_port()
    uvicorn.run("promptflow.service.app:app", port=port, reload=True)
