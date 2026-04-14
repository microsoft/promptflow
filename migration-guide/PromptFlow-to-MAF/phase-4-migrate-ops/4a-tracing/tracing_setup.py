"""
Wires MAF's built-in OpenTelemetry instrumentation to Azure Application Insights.

Replaces: Prompt Flow's built-in run viewer (step-by-step trace per node).

MAF automatically emits OTel spans for every executor invocation, agent call,
and LLM request. Call configure_otel_providers() once at application startup,
before any workflow.run() calls. No instrumentation changes needed in Executor classes.

View traces: Azure Portal → Application Insights → Transaction Search

Prerequisites:
    pip install azure-monitor-opentelemetry
    Set in .env: APPLICATIONINSIGHTS_CONNECTION_STRING
"""

import os

from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import configure_otel_providers

load_dotenv()

# Step 1: Configure Azure Monitor as the export destination for OTel spans.
# This sets up the Application Insights exporter for traces, metrics, and logs.
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)

# Step 2: Enable MAF's built-in instrumentation so that executor transitions,
# agent calls, and LLM requests produce workflow-level spans.
# This must be called AFTER the Azure Monitor exporter is configured and
# BEFORE any workflow.run() calls.
configure_otel_providers()
