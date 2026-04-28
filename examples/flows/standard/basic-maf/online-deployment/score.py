"""
Azure ML managed online endpoint scoring script for the basic-maf workflow.

init() is called once when the container starts.
run(raw_data) is called for each request.
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

    # Add the code root (basic-maf/) to sys.path so workflow.py is importable.
    code_root = Path(__file__).resolve().parents[1]
    if str(code_root) not in sys.path:
        sys.path.insert(0, str(code_root))

    # Optional Application Insights tracing.
    appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from agent_framework.observability import configure_otel_providers

        configure_azure_monitor(connection_string=appinsights_conn)
        configure_otel_providers()

    from workflow import create_workflow

    _create_workflow = create_workflow
    logger.info("Workflow factory loaded successfully.")


def run(raw_data):
    """Called for each scoring request.

    Parameters
    ----------
    raw_data : str
        JSON string, e.g. '{"text": "Hello World!"}'

    Returns
    -------
    dict
        {"answer": str}
    """
    data = json.loads(raw_data)
    text = data.get("text", "").strip()
    if not text:
        raise ValueError("'text' field must not be empty.")

    workflow = _create_workflow()
    result = asyncio.get_event_loop().run_until_complete(workflow.run(text))
    outputs = result.get_outputs()

    if not outputs:
        raise RuntimeError("Workflow produced no output.")

    output = outputs[0]
    # Handle both string outputs and AgentResponse objects.
    if hasattr(output, "text"):
        return {"answer": output.text}
    return {"answer": str(output)}
