"""
Azure ML managed online endpoint scoring script.

Replaces: Prompt Flow Managed Online Endpoint.

init() is called once when the container starts.
run(raw_data) is called for each request; raw_data is the JSON request body.

Deploy:
    bash deploy.sh

Optional: set MAF_WORKFLOW_FILE to your workflow file path
          (default: phase-2-rebuild/01_linear_flow.py).
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

workflow = None


def init():
    """Called once when the endpoint container starts."""
    global workflow

    guide_root = Path(__file__).resolve().parents[2]
    if str(guide_root) not in sys.path:
        sys.path.insert(0, str(guide_root))

    # Optional tracing — only when the connection string is present.
    appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from agent_framework.observability import configure_otel_providers

        configure_azure_monitor(connection_string=appinsights_conn)
        configure_otel_providers()

    from workflow_loader import load_workflow

    workflow = load_workflow()
    logger.info("Workflow loaded successfully.")


def run(raw_data):
    """Called for each scoring request.

    Parameters
    ----------
    raw_data : str
        JSON string with the request body, e.g. '{"question": "..."}'

    Returns
    -------
    dict
        {"answer": str}
    """
    data = json.loads(raw_data)
    question = data.get("question", "").strip()
    if not question:
        raise ValueError("Question must not be empty.")

    result = asyncio.get_event_loop().run_until_complete(workflow.run(question))
    outputs = result.get_outputs()

    if not outputs:
        raise RuntimeError("Workflow produced no output.")

    output = outputs[0]
    # AgentResponse objects are not JSON-serializable; extract the text.
    if hasattr(output, "text"):
        return {"answer": output.text}
    return {"answer": str(output)}
