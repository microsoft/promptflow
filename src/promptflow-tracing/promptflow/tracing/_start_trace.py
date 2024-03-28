# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import typing

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ._constants import (
    PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON,
    RESOURCE_ATTRIBUTES_SERVICE_NAME,
    ResourceAttributesFieldName,
)
from ._integrations._openai_injector import inject_openai_api


def start_trace(
    *,
    resource_attributes: typing.Optional[dict] = None,
    session: typing.Optional[str] = None,
    **kwargs,
):
    """Start a tracing session.

    Instrument `openai`, and set tracer provider for current tracing session.

    :param resource_attributes: Specify the resource attributes for current tracing session.
    :type resource_attributes: typing.Optional[dict]
    :param session: Specify the session id for current tracing session.
    :type session: typing.Optional[str]
    """
    # prepare resource.attributes and set tracer provider
    res_attrs = {ResourceAttributesFieldName.SERVICE_NAME: RESOURCE_ATTRIBUTES_SERVICE_NAME}
    if session is not None:
        res_attrs[ResourceAttributesFieldName.SESSION_ID] = session
    if isinstance(resource_attributes, dict):
        for attr_key, attr_value in resource_attributes.items():
            res_attrs[attr_key] = attr_value
    _set_tracer_provider(res_attrs)

    if _skip_tracing_local_setup():
        return

    if _is_devkit_installed():
        from promptflow._sdk._tracing import start_trace_with_devkit

        start_trace_with_devkit(
            session_id=session,
            attrs=kwargs.get("attributes", None),
            run=kwargs.get("run", None),
        )


def setup_exporter_from_environ() -> None:
    # openai instrumentation
    inject_openai_api()

    if _is_devkit_installed():
        from promptflow._sdk._tracing import setup_exporter_to_pfs

        setup_exporter_to_pfs()


def _skip_tracing_local_setup() -> bool:
    return str(os.getenv(PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON, "false")).lower() == "true"


def _is_tracer_provider_set() -> bool:
    return isinstance(trace.get_tracer_provider(), TracerProvider)


def _is_pf_tracer_provider_set() -> bool:
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        return False
    service_name = provider._resource.attributes.get(ResourceAttributesFieldName.SERVICE_NAME)
    return service_name == RESOURCE_ATTRIBUTES_SERVICE_NAME


def _append_span_processors(current_trace_provider: TracerProvider, tracer_provider: TracerProvider):
    from opentelemetry.sdk.trace import ConcurrentMultiSpanProcessor, SynchronousMultiSpanProcessor

    if not isinstance(current_trace_provider, TracerProvider):
        return
    if not isinstance(
        current_trace_provider._active_span_processor, (ConcurrentMultiSpanProcessor, SynchronousMultiSpanProcessor)
    ):
        return

    # Append all span processors to the new tracer provider
    for processor in current_trace_provider._active_span_processor._span_processors:
        tracer_provider.add_span_processor(processor)


def _force_set_tracer_provider(tracer_provider: TracerProvider) -> None:
    from opentelemetry.trace import _TRACER_PROVIDER_SET_ONCE

    with _TRACER_PROVIDER_SET_ONCE._lock:
        _TRACER_PROVIDER_SET_ONCE._done = False

    #  Append all span processors to the new tracer provider to make sure all span processors are kept
    current_trace_provider = trace.get_tracer_provider()
    _append_span_processors(current_trace_provider, tracer_provider)
    trace.set_tracer_provider(tracer_provider)


def _set_tracer_provider(res_attrs: typing.Dict[str, str]) -> None:
    #  Do not set tracer provider if it is already set by pf
    if _is_pf_tracer_provider_set():
        return

    res = Resource(attributes=res_attrs)
    tracer_provider = TracerProvider(resource=res)
    # Force set tracer provider if it is already set by other codes
    # We will keep all span processors in the current tracer provider when setting the new one
    if _is_tracer_provider_set():
        _force_set_tracer_provider(tracer_provider)
    else:
        trace.set_tracer_provider(tracer_provider)


def _is_devkit_installed() -> bool:
    try:
        from promptflow._sdk._tracing import setup_exporter_to_pfs, start_trace_with_devkit  # noqa: F401

        return True
    except ImportError:
        return False
