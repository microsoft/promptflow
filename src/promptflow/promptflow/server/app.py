import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/execution/flow")
async def flow_test_execution():
    return {"Hello": "World"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
