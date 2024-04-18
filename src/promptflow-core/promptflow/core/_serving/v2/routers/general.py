# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os

from fastapi import APIRouter

from promptflow.core._version import __version__


def get_general_router(swagger):
    router = APIRouter()

    @router.get("/swagger.json")
    async def swagger_json():
        return swagger

    @router.get("/health")
    async def health():
        """Check if the runtime is alive."""
        return {"status": "Healthy", "version": __version__}

    @router.get("/version")
    async def version():
        """Check the runtime's version."""
        build_info = os.environ.get("BUILD_INFO", "")
        try:
            build_info_dict = json.loads(build_info)
            version = build_info_dict["build_number"]
        except Exception:
            version = __version__
        return {"status": "Healthy", "build_info": build_info, "version": version}

    return router
