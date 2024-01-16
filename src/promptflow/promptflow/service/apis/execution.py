from fastapi import APIRouter

from promptflow.service.contracts.base_run_request import BaseRunRequest

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.post("/execution/flow")
async def flow_test_execution(base_run_request: BaseRunRequest):
    print(base_run_request)
    return {"Hello": "World"}
