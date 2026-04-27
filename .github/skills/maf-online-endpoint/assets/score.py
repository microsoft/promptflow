"""
Azure ML managed online endpoint scoring script for MAF workflows.

init() is called once when the container starts.
run(raw_data) is called for each request; raw_data is the JSON request body.

This file lives in online-deployment/ under the project root.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

_create_workflow = None


def init():
    """Called once when the endpoint container starts."""
    global _create_workflow

    # Add the project root to sys.path so workflow modules can be imported.
    # score.py is in online-deployment/ (1 level deep), so parents[1] = project root.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Optional Application Insights tracing.
    appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from agent_framework.observability import configure_otel_providers

        configure_azure_monitor(connection_string=appinsights_conn)
        configure_otel_providers()

    # Import the workflow factory.  Every run() call creates a fresh workflow
    # instance to avoid "Workflow is already running" errors on concurrent
    # requests.
    from workflow import create_workflow

    _create_workflow = create_workflow
    logger.info("Workflow factory loaded successfully.")


def run(raw_data):
    """Called for each scoring request.

    Parameters
    ----------
    raw_data : str
        JSON string with the request body, e.g. '{"text": "..."}'
        Adapt the input key to match what the workflow expects.

    Returns
    -------
    dict
        {"answer": str}
    """
    data = json.loads(raw_data)
    # Adapt input key to match the workflow's expected input.
    # Common keys: "text", "question", "input", "query"
    text = data.get("text", "").strip()
    if not text:
        raise ValueError("'text' field must not be empty.")

    workflow = _create_workflow()
    result = asyncio.get_event_loop().run_until_complete(workflow.run(text))
    outputs = result.get_outputs()

    if not outputs:
        raise RuntimeError("Workflow produced no output.")

    output = outputs[0]
    # AgentResponse objects are not JSON-serializable; extract the text.
    if hasattr(output, "text"):
        return {"answer": output.text}
    return {"answer": str(output)}
