# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import platform
import sys
import threading
import time
import uuid

import psutil
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._sdk._constants import TRACE_SESSION_ID_ENV_VAR
from promptflow._sdk._service.utils.utils import _get_process_by_port, get_port_from_config, is_port_in_use
from promptflow._utils.logger_utils import get_cli_sdk_logger

_logger = get_cli_sdk_logger()


def start_trace():
    """Start a tracing session.

    This will capture OpenAI and prompt flow related calls and persist traces;
    it will also provide a UI url for user to visualize traces details.

    Note that this function is still under preview, and may change at any time.
    """
    pfs_port = get_port_from_config(create_if_not_exists=True)
    _start_pfs_in_background(pfs_port)
    # Start a liveness probe in a new thread
    threading.Thread(target=_liveness_probe, args=(pfs_port,), daemon=True).start()
    _logger.debug("PFS is serving on port %s", pfs_port)
    # provision a session
    # TODO: make this dynamic after set from our side
    # session_id = _provision_session()
    session_id = "8cffec9b-eda9-4dab-a321-4f94227c23cb"
    _logger.debug("current session id is %s", session_id)
    # init the global tracer with endpoint, context (session, run, exp)
    _init_otel_trace_exporter(otlp_port=pfs_port)
    # print user the UI url
    ui_url = f"http://localhost:{pfs_port}/v1.0/ui/traces?session={session_id}"
    print(f"You can view the trace from UI url: {ui_url}")


def _start_pfs_in_background(pfs_port) -> None:
    """Start a pfs process in background."""
    if is_port_in_use(pfs_port):
        _logger.debug("PFS is already serving on port %s", pfs_port)
        return
    args = [sys.executable, "-m", "promptflow._sdk._service.entry", "start"]
    # Start a pfs process using detach mode
    if platform.system() == "Windows":
        os.spawnv(os.P_DETACH, sys.executable, args)
    else:
        os.system(" ".join(["nohup"] + args + ["&"]))


def _liveness_probe(port, interval=60):
    """Send a probe to the specified port every `interval` seconds."""
    while True:
        if not is_port_in_use(port):
            _logger.error(f"PFS port {port} is not responding")
        try:
            # Find the PID of the process that uses the port
            proc = _get_process_by_port(port)
            pid = proc.info["pid"]
            # Get the process status
            status = proc.status()
            _logger.debug(f"Process status: {status}")
        except psutil.NoSuchProcess:
            _logger.error(f"No process with PID {pid} is running")
        time.sleep(interval)


def _provision_session() -> str:
    session_id = str(uuid.uuid4())
    # TODO: need to confirm if it can be inherited by subprocess
    os.environ[TRACE_SESSION_ID_ENV_VAR] = session_id
    return session_id


def _init_otel_trace_exporter(otlp_port: str) -> None:
    resource = Resource(
        attributes={
            SERVICE_NAME: "promptflow",
        }
    )
    trace_provider = TracerProvider(resource=resource)
    endpoint = f"http://localhost:{otlp_port}/v1/traces"
    otlp_span_exporter = OTLPSpanExporter(endpoint=endpoint)
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(trace_provider)
