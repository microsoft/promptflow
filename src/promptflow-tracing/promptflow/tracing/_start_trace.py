# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import importlib.metadata
import inspect
import logging
import os
import typing

from opentelemetry import trace
from opentelemetry.sdk.environment_variables import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from ._constants import (
    PF_TRACING_SKIP_LOCAL_SETUP_ENVIRON,
    RESOURCE_ATTRIBUTES_COLLECTION_DEFAULT,
    RESOURCE_ATTRIBUTES_SERVICE_NAME,
    ResourceAttributesFieldName,
)
from ._integrations._openai_injector import inject_openai_api

TRACER_PROVIDER_PROTECTED_COLLECTION_ATTR = "_protected_collection"


def start_trace(
    *,
    resource_attributes: typing.Optional[dict] = None,
    collection: typing.Optional[str] = None,
    **kwargs,
):
    """Promptflow instrumentation.

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

    # openai instrumentation
    logging.debug("injecting OpenAI API...")
    inject_openai_api()
    logging.debug("OpenAI API injected.")

    # prepare resource.attributes and set tracer provider
    res_attrs = {ResourceAttributesFieldName.SERVICE_NAME: RESOURCE_ATTRIBUTES_SERVICE_NAME}
    if isinstance(resource_attributes, dict):
        logging.debug("specified resource attributes: %s", resource_attributes)
        for attr_key, attr_value in resource_attributes.items():
            res_attrs[attr_key] = attr_value

    # determine collection
    collection_user_specified = collection is not None
    if not collection_user_specified:
        logging.debug("collection is not user specified")
        if is_collection_writeable():
            # internal parameter for devkit call
            _collection = kwargs.get("_collection", None)
            if _collection is not None:
                logging.debug("received internal parameter _collection: %s, will use this", _collection)
                collection = _collection
            else:
                logging.debug("trying to get from current working directory...")
                collection = _get_collection_from_cwd()
        else:
            logging.debug("collection is protected, will directly use that...")
            tracer_provider: TracerProvider = trace.get_tracer_provider()
            collection = tracer_provider.resource.attributes[ResourceAttributesFieldName.COLLECTION]
    logging.info("collection: %s", collection)
    res_attrs[ResourceAttributesFieldName.COLLECTION] = collection
    logging.info("resource attributes: %s", res_attrs)

    # if user specifies collection, we will add a flag on tracer provider to avoid override
    _set_tracer_provider(res_attrs, protected_collection=collection_user_specified)

    if _is_devkit_installed():
        from promptflow._sdk._tracing import start_trace_with_devkit

        logging.debug("promptflow-devkit is installed.")

        # in promptflow-devkit<=1.8.0, `start_trace_with_devkit` cannot accept `**kwargs`
        # so we need to handle this with function signature check, and warn user on this
        if _kwargs_in_func(start_trace_with_devkit):
            logging.debug("compatible promptflow-devkit version, will pass `collection` and `kwargs`...")
            logging.debug("collection: %s", collection)
            logging.debug("kwargs: %s", kwargs)
            start_trace_with_devkit(collection=collection, **kwargs)
        else:
            warning_msg = (
                "incompatible `promptflow-devkit` version installed, which may lead to unexpected behavior; "
                "it is recommended to use 'promptflow-devkit>=1.9.0' for better trace experience."
            )
            logging.warning(warning_msg)
            print(warning_msg)
            logging.debug("will pass `collection`, `attributes`, and `run`...")
            _attributes = kwargs.get("attributes", None)
            _run = kwargs.get("run", None)
            logging.debug("collection: %s", collection)
            logging.debug("attributes: %s", _attributes)
            logging.debug("run: %s", _run)
            start_trace_with_devkit(collection=collection, attributes=_attributes, run=_run)


def setup_exporter_from_environ() -> None:
    # openai instrumentation
    logging.debug("injecting OpenAI API...")
    inject_openai_api()
    logging.debug("OpenAI API injected.")

    # Ignore all the setup if the endpoint is not set
    otlp_endpoint = os.getenv(OTEL_EXPORTER_OTLP_ENDPOINT)
    logging.debug("environ OTEL_EXPORTER_OTLP_ENDPOINT: %s", otlp_endpoint)
    otlp_traces_endpoint = os.getenv(OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)
    logging.debug("environ OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: %s", otlp_traces_endpoint)
    endpoint = otlp_traces_endpoint or otlp_endpoint
    if not endpoint:
        logging.info("environ OTLP endpoint is not set, will skip the following setup.")
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


def _set_tracer_provider(res_attrs: typing.Dict[str, str], protected_collection: bool) -> None:
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

    if protected_collection:
        logging.info("user specifies collection, will add a flag on tracer provider to avoid override...")
        setattr(trace.get_tracer_provider(), TRACER_PROVIDER_PROTECTED_COLLECTION_ATTR, True)


def is_collection_writeable() -> bool:
    return not getattr(trace.get_tracer_provider(), TRACER_PROVIDER_PROTECTED_COLLECTION_ATTR, False)


def _is_devkit_installed() -> bool:
    try:
        importlib.metadata.version("promptflow-devkit")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def _kwargs_in_func(func: typing.Callable) -> bool:
    signature = inspect.signature(func)
    params = signature.parameters.values()
    return any(param.kind == param.VAR_KEYWORD for param in params)
