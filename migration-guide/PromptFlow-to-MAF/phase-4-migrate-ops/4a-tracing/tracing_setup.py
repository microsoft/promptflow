"""
Wires MAF's built-in OpenTelemetry instrumentation to Azure Application Insights.

Replaces: Prompt Flow's built-in run viewer (step-by-step trace per node).

MAF automatically emits OTel spans for every executor invocation, agent call,
and LLM request. Call configure_azure_monitor() once at application startup,
before any workflow.run() calls. No instrumentation changes needed in Executor classes.

View traces: Azure Portal → Application Insights → Transaction Search

Prerequisites:
    pip install azure-monitor-opentelemetry
    Set in .env: APPLICATIONINSIGHTS_CONNECTION_STRING
"""

import os

from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor

load_dotenv()

configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)
