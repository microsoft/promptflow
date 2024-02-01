# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import platform
import sys
import time
import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._constants import TRACE_SESSION_ID_ENV_VAR
from promptflow._sdk._service.utils.utils import check_pfs_service_status
from promptflow._utils.logger_utils import get_cli_sdk_logger

_logger = get_cli_sdk_logger()
time_threshold = 30
time_delay = 5


def start_trace():
    """Start a tracing session.

    This will capture OpenAI and prompt flow related calls and persist traces;
    it will also provide a UI url for user to visualize traces details.

    Note that this function is still under preview, and may change at any time.
    """
    from promptflow._sdk._service.utils.utils import get_port_from_config

    pfs_port = get_port_from_config(create_if_not_exists=True)
    _start_pfs_in_background(pfs_port)
    _logger.debug("PFS is serving on port %s", pfs_port)
    # provision a session
    session_id = _provision_session()
    _logger.debug("current session id is %s", session_id)
    # init the global tracer with endpoint, context (session, run, exp)
    _init_otel_trace_exporter(otlp_port=pfs_port)
    # print user the UI url
    ui_url = f"http://localhost:{pfs_port}/v1.0/ui/traces?session={session_id}"
    print(f"You can view the trace from UI url: {ui_url}")


def _start_pfs_in_background(pfs_port) -> None:
    """Start a pfs process in background."""
    from promptflow._sdk._service.utils.utils import is_port_in_use

    args = [sys.executable, "-m", "promptflow._sdk._service.entry", "start", "--port", str(pfs_port)]
    if is_port_in_use(pfs_port):
        _logger.warning(f"Service port {pfs_port} is used.")
        if check_pfs_service_status(pfs_port) is True:
            return
        else:
            args += ["--force"]
    # Start a pfs process using detach mode
    if platform.system() == "Windows":
        os.spawnv(os.P_DETACH, sys.executable, args)
    else:
        os.system(" ".join(["nohup"] + args + ["&"]))

    wait_time = time_delay
    time.sleep(time_delay)
    is_healthy = check_pfs_service_status(pfs_port)
    while is_healthy is False and time_threshold > wait_time:
        _logger.info(
            f"Pfs service is not ready. It has been waited for {wait_time}s, will wait for at most "
            f"{time_threshold}s."
        )
        wait_time += time_delay
        time.sleep(time_delay)
        is_healthy = check_pfs_service_status(pfs_port)

    if is_healthy is False:
        _logger.error(f"Pfs service start failed in {pfs_port}.")
        sys.exit(1)


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
