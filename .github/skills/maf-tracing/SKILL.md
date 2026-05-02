---
name: maf-tracing
description: "Enable tracing and logging for Microsoft Agent Framework (MAF) workflows. Configures OpenTelemetry export to Azure Application Insights and/or a generic OTLP endpoint using environment variables. Adds required packages to requirements.txt. WHEN: enable tracing, add tracing, enable logging, add logging, configure telemetry, Application Insights for MAF, OTLP export, observe workflow, monitor agent workflow, trace agent framework, instrument MAF, add observability, trace workflow executions, debug workflow."
license: MIT
metadata:
  author: Team
  version: "1.0.0"
---

# Enable Tracing & Logging for MAF Workflows

> Configure OpenTelemetry-based tracing for Microsoft Agent Framework workflows, exporting to Azure Application Insights and/or a generic OTLP endpoint.

## Triggers

Activate this skill when the user wants to:
- Enable tracing or logging for a MAF workflow
- Export telemetry to Azure Application Insights
- Export traces to an OTLP-compatible endpoint (Jaeger, Zipkin, Grafana Tempo, etc.)
- Add observability or monitoring to an `agent-framework` project
- Debug or inspect executor/agent/LLM spans in a MAF workflow

## Background

MAF automatically emits OpenTelemetry spans for every executor invocation, agent call, and LLM request. No instrumentation changes are needed inside `Executor` classes. You only need to:

1. **Configure an exporter** — where spans are sent (Application Insights, OTLP endpoint, or both)
2. **Call `configure_otel_providers()`** — activates MAF's built-in instrumentation

This must happen **once at application startup**, before any `workflow.run()` calls.

---

## Rules

1. **Read the user's project first** — Check for an existing `requirements.txt`, `.env`, and entry-point script (e.g., `main.py`, `app.py`, `run_*.py`).
2. **Ask what export destination(s) are needed** — Application Insights, OTLP endpoint, or both. If unclear, default to both.
3. **Do not modify Executor classes** — MAF tracing is automatic. Never add manual `tracer.start_span()` calls inside `@handler` methods unless the user explicitly asks for custom spans.
4. **Call order matters** — Exporter configuration must happen BEFORE `configure_otel_providers()`, and both must happen BEFORE any `workflow.run()`.
5. **Add packages to `requirements.txt`** — Append only the packages the user needs (see Packages section). Do not duplicate existing entries.
6. **Use environment variables** — Never hardcode connection strings or endpoints. Always read from `os.environ` or `.env`.
7. **Generate `.env.example`** — Provide a template showing which environment variables are required.
8. **Python logging integration** — When the user asks for logging (not just tracing), also configure the Python `logging` module to export via OpenTelemetry using `opentelemetry-sdk` log handler.

---

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights | Connection string from Azure Portal → App Insights → Overview |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP export | Base URL of the OTLP collector (e.g., `http://localhost:4318`) |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP export (traces only) | Overrides the base endpoint for trace signals only |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP export | Protocol: `http/protobuf` (default) or `grpc` |
| `OTEL_SERVICE_NAME` | Optional | Service name shown in trace backends (defaults to Python process name) |

> `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` takes precedence over `OTEL_EXPORTER_OTLP_ENDPOINT` for traces.

---

## Packages

| Package | Version | When Needed |
|---------|---------|-------------|
| `agent-framework` | >=1.0.1 | Always (provides `configure_otel_providers`) |
| `azure-monitor-opentelemetry` | >=1.6.4 | Application Insights export |
| `opentelemetry-exporter-otlp-proto-http` | >=1.25.0 | OTLP/HTTP export |
| `opentelemetry-exporter-otlp-proto-grpc` | >=1.25.0 | OTLP/gRPC export (only if `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`) |
| `opentelemetry-sdk` | >=1.25.0 | Custom spans or Python logging integration |
| `python-dotenv` | any | Loading `.env` files |

---

## Setup Patterns

### Pattern A: Application Insights Only

Use when the user wants to send traces to Azure Application Insights.

**Required env var:** `APPLICATIONINSIGHTS_CONNECTION_STRING`

**Required packages:**
```
azure-monitor-opentelemetry>=1.6.4
```

**Setup code** (add at the top of the entry-point script, before `workflow.run()`):

```python
import os
from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor
from agent_framework.observability import configure_otel_providers

load_dotenv()

# Step 1: Configure Azure Monitor exporter (traces, metrics, logs → App Insights)
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)

# Step 2: Enable MAF's built-in instrumentation (executor, agent, LLM spans)
configure_otel_providers()
```

### Pattern B: OTLP Endpoint Only

Use when the user wants to send traces to a generic OTLP-compatible backend (Jaeger, Grafana Tempo, Aspire Dashboard, etc.).

**Required env var:** `OTEL_EXPORTER_OTLP_ENDPOINT`

**Required packages:**
```
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp-proto-http>=1.25.0
```

**Setup code:**

```python
import os
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from agent_framework.observability import configure_otel_providers

load_dotenv()

# Step 1: Set up the OTLP exporter with a TracerProvider
resource = Resource.create({
    "service.name": os.environ.get("OTEL_SERVICE_NAME", "maf-workflow"),
})
tracer_provider = TracerProvider(resource=resource)

otlp_exporter = OTLPSpanExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)

# Step 2: Enable MAF's built-in instrumentation
configure_otel_providers()
```

### Pattern C: Both Application Insights and OTLP

Use when the user wants dual export — Application Insights for Azure-native monitoring plus an OTLP backend for local/third-party observability.

**Required env vars:** `APPLICATIONINSIGHTS_CONNECTION_STRING`, `OTEL_EXPORTER_OTLP_ENDPOINT`

**Required packages:**
```
azure-monitor-opentelemetry>=1.6.4
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp-proto-http>=1.25.0
```

**Setup code:**

```python
import os
from dotenv import load_dotenv
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from agent_framework.observability import configure_otel_providers

load_dotenv()

# Step 1a: Configure Azure Monitor (sets up its own TracerProvider internally)
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)

# Step 1b: Add OTLP exporter to the existing TracerProvider
otlp_endpoint = (
    os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
)
if otlp_endpoint:
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    tracer_provider: TracerProvider = trace.get_tracer_provider()
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Step 2: Enable MAF's built-in instrumentation
configure_otel_providers()
```

### Pattern D: Python Logging via OpenTelemetry

Use when the user also wants Python `logging` calls to be exported alongside traces.

**Additional packages (on top of Pattern A, B, or C):**
```
opentelemetry-sdk>=1.25.0
```

**Setup code** (add after the exporter setup, before `configure_otel_providers()`):

```python
import logging
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry._logs import set_logger_provider

# If using Application Insights, configure_azure_monitor() already handles log export.
# If using OTLP only, set up the OTLP log exporter:
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
    ))
)
set_logger_provider(logger_provider)

# Bridge Python logging to OpenTelemetry
from opentelemetry.instrumentation.logging import LoggingInstrumentor
LoggingInstrumentor().instrument(set_logging_format=True)
```

> **Note:** When using `azure-monitor-opentelemetry` (Pattern A/C), `configure_azure_monitor()` already captures Python logs by default. The above is only needed for OTLP-only setups.

---

## Implementation Steps

### Step 1: Determine export destination(s)

Ask the user or infer from context:
- Application Insights → Pattern A
- OTLP endpoint → Pattern B
- Both → Pattern C

If the user says "tracing" without specifying a destination, default to Pattern C (both).

### Step 2: Update `requirements.txt`

Append the required packages. Do **not** duplicate existing entries. Example additions for Pattern C:

```
azure-monitor-opentelemetry>=1.6.4
opentelemetry-sdk>=1.25.0
opentelemetry-exporter-otlp-proto-http>=1.25.0
```

### Step 3: Create or update `.env.example`

Add the environment variables relevant to the chosen pattern:

```bash
# === Tracing & Observability ===
# Application Insights (Azure Portal → App Insights → Overview → Connection String)
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=https://xxx.in.applicationinsights.azure.com/

# OTLP endpoint (e.g., Jaeger, Grafana Tempo, Aspire Dashboard)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Optional: override service name in trace backends
OTEL_SERVICE_NAME=my-maf-workflow
```

### Step 4: Add tracing setup to entry-point script

Insert the setup code from the appropriate pattern at the **top** of the entry-point script (after imports, before any `workflow.run()` call). The setup must execute once at module load / application startup.

**Placement rules:**
- If the entry point uses `asyncio.run(main())`, place setup code inside `main()` before `workflow.run()`.
- If the entry point is a module-level script, place setup code after imports and `load_dotenv()`.
- If the entry point is a web server (FastAPI, Flask), place setup code in the application factory or startup event.

### Step 5: Verify

1. Run the workflow and check that traces appear in the configured destination.
2. For Application Insights: Azure Portal → Application Insights → Transaction Search → filter by "Dependency" or "Request".
3. For OTLP: Check the collector backend UI (e.g., Jaeger UI at `http://localhost:16686`).

---

## Gotchas

1. **Call order matters** — `configure_azure_monitor()` and/or OTLP exporter setup must happen BEFORE `configure_otel_providers()`. If reversed, MAF spans won't be exported.
2. **`configure_otel_providers()` must run BEFORE `workflow.run()`** — Otherwise, executor-level spans are not generated.
3. **Do not call setup code inside Executors** — Tracing setup is application-level, not per-request. Calling it inside a `@handler` method will create duplicate exporters and corrupt traces.
4. **`configure_azure_monitor()` creates its own TracerProvider** — When combining with OTLP (Pattern C), add the OTLP exporter to the existing provider via `trace.get_tracer_provider()` rather than creating a new `TracerProvider`.
5. **Missing `configure_otel_providers()`** — Without this call, you'll see Application Insights or OTLP infrastructure telemetry but no MAF-specific spans (executor transitions, agent calls, LLM requests).
6. **Connection string format** — The `APPLICATIONINSIGHTS_CONNECTION_STRING` starts with `InstrumentationKey=` followed by a GUID. Do not confuse it with the Instrumentation Key alone.
7. **OTLP endpoint trailing path** — `OTEL_EXPORTER_OTLP_ENDPOINT` should be the base URL (e.g., `http://localhost:4318`). The SDK appends `/v1/traces` automatically. Do not include `/v1/traces` in the env var.
8. **gRPC vs HTTP** — Default protocol is `http/protobuf` (port 4318). If the collector uses gRPC (port 4317), set `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and install `opentelemetry-exporter-otlp-proto-grpc` instead.

---

## Example: Complete Entry Point with Tracing

```python
"""Entry point for a MAF workflow with full tracing setup."""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


def setup_tracing():
    """Configure telemetry exporters and MAF instrumentation. Call once at startup."""
    from agent_framework.observability import configure_otel_providers

    # Application Insights
    appinsights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=appinsights_conn)

    # OTLP endpoint (optional, additive)
    otlp_endpoint = (
        os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    if otlp_endpoint:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider = trace.get_tracer_provider()

        # If Azure Monitor already set a TracerProvider, reuse it; otherwise create one
        if not isinstance(tracer_provider, TracerProvider):
            resource = Resource.create({
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "maf-workflow"),
            })
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)

        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Enable MAF's built-in spans (must be last)
    configure_otel_providers()


async def main():
    setup_tracing()

    # Import and run your workflow here
    from workflow import create_workflow

    workflow = create_workflow()
    result = await workflow.run("Hello, world!")
    print(result.get_outputs())


if __name__ == "__main__":
    asyncio.run(main())
```
