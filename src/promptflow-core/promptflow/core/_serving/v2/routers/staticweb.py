# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


def get_staticweb_router(logger, static_folder: str):
    router = APIRouter()
    templates = Jinja2Templates(directory=static_folder) if static_folder else None

    @router.get("/", response_class=HTMLResponse)
    @router.post("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Show the home page."""
        logger.info("Request to home page.")
        index_path = Path(static_folder) / "index.html" if static_folder else None
        logger.info(f"Index path: {index_path}")
        if index_path and index_path.exists():
            return templates.TemplateResponse(request=request, name="index.html", context={})
        else:
            return "<h1>Welcome to promptflow app.</h1>"

    return router
