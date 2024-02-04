# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import typing
import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from promptflow._constants import SpanAttributeFieldName
from promptflow._core.openai_injector import inject_openai_api
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._service.utils.utils import is_pfs_service_healthy
from promptflow._utils.logger_utils import get_cli_sdk_logger

_logger = get_cli_sdk_logger()


def start_trace(*, session: typing.Optional[str] = None, **kwargs):
    """Start a tracing session.

    This will capture OpenAI and prompt flow related calls and persist traces;
    it will also provide a UI url for user to visualize traces details.

    Note that this function is still under preview, and may change at any time.
    """
    from promptflow._sdk._constants import ExperimentContextKey
    from promptflow._sdk._service.utils.utils import get_port_from_config

    pfs_port = get_port_from_config(create_if_not_exists=True)
    _start_pfs(pfs_port)
    _logger.debug("PFS is serving on port %s", pfs_port)

    # provision a session
    session_id = _provision_session(session_id=session)
    _logger.debug("current session id is %s", session_id)

    operation_context = OperationContext.get_instance()

    # honor and set attributes if user has specified
    attributes: dict = kwargs.get("attributes", None)
    if attributes is not None:
        for attr_key, attr_value in attributes.items():
            operation_context._add_otel_attributes(attr_key, attr_value)

    # prompt flow related, retrieve `experiment` and `referenced.line_run_id`
    experiment = os.environ.get(ExperimentContextKey.EXPERIMENT, None)
    if experiment is not None:
        operation_context._add_otel_attributes(SpanAttributeFieldName.EXPERIMENT, experiment)
    ref_line_run_id = os.environ.get(ExperimentContextKey.REFERENCED_LINE_RUN_ID, None)
    if ref_line_run_id is not None:
        operation_context._add_otel_attributes(SpanAttributeFieldName.REFERENCED_LINE_RUN_ID, ref_line_run_id)

    # init the global tracer with endpoint
    _init_otel_trace_exporter(otlp_port=pfs_port)
    # openai instrumentation
    inject_openai_api()
    # print user the UI url
    ui_url = f"http://localhost:{pfs_port}/v1.0/ui/traces?session={session_id}"
    print(f"You can view the trace from UI url: {ui_url}")


def _start_pfs(pfs_port) -> None:
    from promptflow._sdk._service.entry import PF_NO_INTERACTIVE_LOGIN, entry
    from promptflow._sdk._service.utils.utils import is_port_in_use

    command_args = ["start", "--port", str(pfs_port)]
    if is_port_in_use(pfs_port):
        _logger.warning(f"Service port {pfs_port} is used.")
        if is_pfs_service_healthy(pfs_port) is True:
            return
        else:
            command_args += ["--force"]
    os.environ[PF_NO_INTERACTIVE_LOGIN] = "true"
    entry(command_args)


def _provision_session(session_id: typing.Optional[str] = None) -> str:
    operation_context = OperationContext.get_instance()

    # user has specified a session id, honor and directly return it
    if session_id is not None:
        operation_context._add_otel_attributes(SpanAttributeFieldName.SESSION_ID, session_id)
        return session_id

    # session id is already in operation context, directly return
    otel_attributes = operation_context._get_otel_attributes()
    if SpanAttributeFieldName.SESSION_ID in otel_attributes:
        return otel_attributes[SpanAttributeFieldName.SESSION_ID]

    # provision a new session id
    session_id = str(uuid.uuid4())
    operation_context._add_otel_attributes(SpanAttributeFieldName.SESSION_ID, session_id)
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
