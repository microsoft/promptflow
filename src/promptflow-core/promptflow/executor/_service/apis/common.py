# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from promptflow._utils.feature_utils import get_feature_list
from promptflow.executor._service.utils.service_utils import get_executor_version

router = APIRouter()


@router.get("/health")
def health_check():
    return PlainTextResponse("healthy")


@router.get("/version")
def version():
    return {
        "status": "healthy",
        "version": get_executor_version(),
        "feature_list": get_feature_list(),
    }
