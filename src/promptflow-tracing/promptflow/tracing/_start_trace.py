# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib.metadata
import logging
import os
import typing

from opentelemetry import trace
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ._constants import (
    PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON,
    RESOURCE_ATTRIBUTES_COLLECTION_DEFAULT,
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
        logging.info("skip tracing local setup as the environment variable is set.")
        return

    if collection is None:
        logging.debug("collection is not specified, trying to get from current working directory...")
        collection = _get_collection_from_cwd()
    logging.info("collection: %s", collection)

    # prepare resource.attributes and set tracer provider
    res_attrs = {
        ResourceAttributesFieldName.SERVICE_NAME: RESOURCE_ATTRIBUTES_SERVICE_NAME,
        ResourceAttributesFieldName.COLLECTION: collection,
    }
    if isinstance(resource_attributes, dict):
        logging.debug("specified resource attributes: %s", resource_attributes)
        for attr_key, attr_value in resource_attributes.items():
            res_attrs[attr_key] = attr_value
    logging.info("resource attributes: %s", res_attrs)

    _set_tracer_provider(res_attrs)

    if _is_devkit_installed():
        from promptflow._sdk._tracing import start_trace_with_devkit

        logging.debug("promptflow-devkit is installed, will continue local setup...")
        logging.debug("collection: %s", collection)
        logging.debug("kwargs: %s", kwargs)
        start_trace_with_devkit(collection=collection, **kwargs)


def setup_exporter_from_environ() -> None:
    # openai instrumentation
    logging.debug("injecting OpenAI API...")
    inject_openai_api()
    logging.debug("OpenAI API injected.")

    # Ignore all the setup if the endpoint is not set
    endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    logging.debug("environ OTEL_EXPORTER_OTLP_ENDPOINT: %s", endpoint)
    if not endpoint:
        logging.info("environ OTEL_EXPORTER_OTLP_ENDPOINT is not set, will skip the following setup.")
        return

    if _is_devkit_installed():
        from promptflow._sdk._tracing import setup_exporter_to_pfs

        logging.debug("promptflow-devkit is installed, will continue local setup...")
        setup_exporter_to_pfs()


def _skip_tracing_local_setup() -> bool:
    return str(os.getenv(PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON, "false")).lower() == "true"


def _get_collection_from_cwd() -> str:
    """Try to use cwd folder name as collection name; will fall back to default value if run into exception."""
    cur_folder_name = ""
    try:
        cwd = os.getcwd()
        cur_folder_name = os.path.basename(cwd)
    except Exception:  # pylint: disable=broad-except
        # possible exception: PermissionError, FileNotFoundError, OSError, etc.
        pass
    collection = cur_folder_name if cur_folder_name != "" else RESOURCE_ATTRIBUTES_COLLECTION_DEFAULT
    return collection


def _set_tracer_provider(res_attrs: typing.Dict[str, str]) -> None:
    res = Resource(attributes=res_attrs)
    tracer_provider = TracerProvider(resource=res)

    cur_tracer_provider = trace.get_tracer_provider()
    if isinstance(cur_tracer_provider, TracerProvider):
        logging.info("tracer provider is already set, will merge the resource attributes...")
        cur_res = cur_tracer_provider.resource
        logging.debug("current resource: %s", cur_res.attributes)
        new_res = cur_res.merge(res)
        cur_tracer_provider._resource = new_res
        logging.info("tracer provider is updated with resource attributes: %s", new_res.attributes)
    else:
        trace.set_tracer_provider(tracer_provider)
        logging.info("tracer provider is set with resource attributes: %s", res.attributes)


def _is_devkit_installed() -> bool:
    try:
        importlib.metadata.version("promptflow-devkit")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False
