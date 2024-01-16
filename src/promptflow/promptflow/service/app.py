import uvicorn
from fastapi import FastAPI

from promptflow.service.apis.execution import router as execution_router

app = FastAPI()
app.include_router(execution_router)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
