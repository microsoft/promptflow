# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import typing

from opentelemetry import trace
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
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
    collection: typing.Optional[str] = None,
    **kwargs,
):
    """Promptflow instrumentation.

    Instrument `openai`, and set tracer provider for current process.

    :param resource_attributes: Specify the resource attributes for current process.
    :type resource_attributes: typing.Optional[dict]
    :param collection: Specify the collection for current tracing.
    :type collection: typing.Optional[str]
    """

    # When PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON is set to true, the start_trace should be skipped.
    # An example is that user call start_trace at cloud mode. Nothing should happen.
    if _skip_tracing_local_setup():
        return

    # prepare resource.attributes and set tracer provider
    res_attrs = {ResourceAttributesFieldName.SERVICE_NAME: RESOURCE_ATTRIBUTES_SERVICE_NAME}
    if collection is not None:
        res_attrs[ResourceAttributesFieldName.COLLECTION] = collection
    if isinstance(resource_attributes, dict):
        for attr_key, attr_value in resource_attributes.items():
            res_attrs[attr_key] = attr_value
    _set_tracer_provider(res_attrs)

    if _is_devkit_installed():
        from promptflow._sdk._tracing import start_trace_with_devkit

        start_trace_with_devkit(
            collection=collection,
            attrs=kwargs.get("attributes", None),
            run=kwargs.get("run", None),
        )


def setup_exporter_from_environ() -> None:

    # openai instrumentation
    inject_openai_api()

    # Ignore all the setup if the endpoint is not set
    endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    if not endpoint:
        return

    if _is_devkit_installed():
        from promptflow._sdk._tracing import setup_exporter_to_pfs

        setup_exporter_to_pfs()


def _skip_tracing_local_setup() -> bool:
    return str(os.getenv(PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON, "false")).lower() == "true"


def _is_tracer_provider_set() -> bool:
    return isinstance(trace.get_tracer_provider(), TracerProvider)


def _force_set_tracer_provider(tracer_provider: TracerProvider) -> None:
    from opentelemetry.trace import _TRACER_PROVIDER_SET_ONCE

    with _TRACER_PROVIDER_SET_ONCE._lock:
        _TRACER_PROVIDER_SET_ONCE._done = False

    trace.set_tracer_provider(tracer_provider)


def _set_tracer_provider(res_attrs: typing.Dict[str, str]) -> None:
    res = Resource(attributes=res_attrs)
    tracer_provider = TracerProvider(resource=res)
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
