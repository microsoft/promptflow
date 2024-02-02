# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from promptflow._utils.feature_utils import get_feature_list
from promptflow._version import VERSION

router = APIRouter()


@router.get("/health")
async def health_check():
    return PlainTextResponse("healthy")


@router.get("/version")
async def version():
    build_info = os.environ.get("BUILD_INFO", "")
    try:
        build_info_dict = json.loads(build_info)
        version = build_info_dict["build_number"]
    except Exception:
        version = VERSION

    return {
        "status": "healthy",
        "build_info": build_info,
        "version": version,
        "feature_list": get_feature_list(),
    }
