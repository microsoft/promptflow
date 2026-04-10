"""
Wraps a MAF workflow in a FastAPI service.

Replaces: Prompt Flow Managed Online Endpoint.

The /ask endpoint accepts {"question": str} and returns {"answer": str}.

Run locally:
    uvicorn app:app --reload

Deploy:
    bash deploy.sh

Optional: set MAF_WORKFLOW_FILE to your workflow file path
          (default: phase-2-rebuild/01_linear_flow.py).
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from azure.monitor.opentelemetry import configure_azure_monitor

GUIDE_ROOT = Path(__file__).resolve().parents[2]
if str(GUIDE_ROOT) not in sys.path:
    sys.path.insert(0, str(GUIDE_ROOT))

from workflow_loader import load_workflow

load_dotenv()

workflow = load_workflow()

# Tracing is optional — only configured when the connection string is present.
# Set APPLICATIONINSIGHTS_CONNECTION_STRING in .env to enable Application Insights.
_appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _appinsights_conn:
    configure_azure_monitor(connection_string=_appinsights_conn)


class QuestionRequest(BaseModel):
    question: str


class AnswerResponse(BaseModel):
    answer: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="MAF Workflow Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
async def ask(payload: QuestionRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    result = await workflow.run(payload.question.strip())
    outputs = result.get_outputs()

    if not outputs:
        raise HTTPException(status_code=500, detail="Workflow produced no output.")

    return AnswerResponse(answer=outputs[0])
