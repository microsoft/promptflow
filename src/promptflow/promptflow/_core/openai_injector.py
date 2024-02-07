# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import functools
import importlib
import logging
import os
from importlib.metadata import version

import openai

from promptflow._core.operation_context import OperationContext
from promptflow.contracts.trace import TraceType

from .tracer import _traced_async, _traced_sync

USER_AGENT_HEADER = "x-ms-useragent"
PROMPTFLOW_PREFIX = "ms-azure-ai-promptflow-"
IS_LEGACY_OPENAI = version("openai").startswith("0.")


def inject_function_async(args_to_ignore=None, trace_type=TraceType.LLM):
    def decorator(func):
        return _traced_async(func, args_to_ignore=args_to_ignore, trace_type=trace_type)

    return decorator


def inject_function_sync(args_to_ignore=None, trace_type=TraceType.LLM):
    def decorator(func):
        return _traced_sync(func, args_to_ignore=args_to_ignore, trace_type=trace_type)

    return decorator


def get_aoai_telemetry_headers() -> dict:
    """Get the http headers for AOAI request.

    The header, whose name starts with "ms-azure-ai-" or "x-ms-", is used to track the request in AOAI. The
    value in this dict will be recorded as telemetry, so please do not put any sensitive information in it.

    Returns:
        A dictionary of http headers.
    """
    # get promptflow info from operation context
    operation_context = OperationContext.get_instance()
    tracking_info = operation_context._get_tracking_info()
    tracking_info = {k.replace("_", "-"): v for k, v in tracking_info.items()}

    def is_primitive(value):
        return value is None or isinstance(value, (int, float, str, bool))

    #  Ensure that the telemetry info is primitive
    tracking_info = {k: v for k, v in tracking_info.items() if is_primitive(v)}

    # init headers
    headers = {USER_AGENT_HEADER: operation_context.get_user_agent()}

    # update header with promptflow info
    headers.update({f"{PROMPTFLOW_PREFIX}{k}": str(v) if v is not None else "" for k, v in tracking_info.items()})

    return headers


def inject_operation_headers(f):
    def inject_headers(kwargs):
        # Inject headers from operation context, overwrite injected header with headers from kwargs.
        injected_headers = get_aoai_telemetry_headers()
        original_headers = kwargs.get("headers" if IS_LEGACY_OPENAI else "extra_headers")
        if original_headers and isinstance(original_headers, dict):
            injected_headers.update(original_headers)
        kwargs["headers" if IS_LEGACY_OPENAI else "extra_headers"] = injected_headers

    if asyncio.iscoroutinefunction(f):

        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            inject_headers(kwargs)
            return await f(*args, **kwargs)

    else:

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            inject_headers(kwargs)
            return f(*args, **kwargs)

    return wrapper


def inject_async(f):
    wrapper_fun = inject_operation_headers((inject_function_async(["api_key", "headers", "extra_headers"])(f)))
    wrapper_fun._original = f
    return wrapper_fun


def inject_sync(f):
    wrapper_fun = inject_operation_headers((inject_function_sync(["api_key", "headers", "extra_headers"])(f)))
    wrapper_fun._original = f
    return wrapper_fun


def _openai_api_list():
    if IS_LEGACY_OPENAI:
        sync_apis = (
            ("openai", "Completion", "create"),
            ("openai", "ChatCompletion", "create"),
            ("openai", "Embedding", "create"),
        )

        async_apis = (
            ("openai", "Completion", "acreate"),
            ("openai", "ChatCompletion", "acreate"),
            ("openai", "Embedding", "acreate"),
        )
    else:
        sync_apis = (
            ("openai.resources.chat", "Completions", "create"),
            ("openai.resources", "Completions", "create"),
            ("openai.resources", "Embeddings", "create"),
        )

        async_apis = (
            ("openai.resources.chat", "AsyncCompletions", "create"),
            ("openai.resources", "AsyncCompletions", "create"),
            ("openai.resources", "AsyncEmbeddings", "create"),
        )

    yield sync_apis, inject_sync
    yield async_apis, inject_async


def _generate_api_and_injector(apis):
    for apis, injector in apis:
        for module_name, class_name, method_name in apis:
            try:
                module = importlib.import_module(module_name)
                api = getattr(module, class_name)
                if hasattr(api, method_name):
                    yield api, method_name, injector
            except AttributeError as e:
                # Log the attribute exception with the missing class information
                logging.warning(
                    f"AttributeError: The module '{module_name}' does not have the class '{class_name}'. {str(e)}"
                )
            except Exception as e:
                # Log other exceptions as a warning, as we're not sure what they might be
                logging.warning(f"An unexpected error occurred: {str(e)}")


def available_openai_apis_and_injectors():
    """
    Generates a sequence of tuples containing OpenAI API classes, method names, and
    corresponding injector functions based on whether the legacy OpenAI interface is used.

    This function handles the discrepancy reported in https://github.com/openai/openai-python/issues/996,
    where async interfaces were not recognized as coroutines. It ensures that decorators
    are applied correctly to both synchronous and asynchronous methods.

    Yields:
        Tuples of (api_class, method_name, injector_function)
    """
    yield from _generate_api_and_injector(_openai_api_list())


def inject_openai_api():
    """This function:
    1. Modifies the create methods of the OpenAI API classes to inject logic before calling the original methods.
    It stores the original methods as _original attributes of the create methods.
    2. Updates the openai api configs from environment variables.
    """

    for api, method, injector in available_openai_apis_and_injectors():
        # Check if the create method of the openai_api class has already been modified
        if not hasattr(getattr(api, method), "_original"):
            setattr(api, method, injector(getattr(api, method)))

    if IS_LEGACY_OPENAI:
        # For the openai versions lower than 1.0.0, it reads api configs from environment variables only at
        # import time. So we need to update the openai api configs from environment variables here.
        # Please refer to this issue: https://github.com/openai/openai-python/issues/557.
        # The issue has been fixed in openai>=1.0.0.
        openai.api_key = os.environ.get("OPENAI_API_KEY", openai.api_key)
        openai.api_key_path = os.environ.get("OPENAI_API_KEY_PATH", openai.api_key_path)
        openai.organization = os.environ.get("OPENAI_ORGANIZATION", openai.organization)
        openai.api_base = os.environ.get("OPENAI_API_BASE", openai.api_base)
        openai.api_type = os.environ.get("OPENAI_API_TYPE", openai.api_type)
        openai.api_version = os.environ.get("OPENAI_API_VERSION", openai.api_version)


def recover_openai_api():
    """This function restores the original create methods of the OpenAI API classes
    by assigning them back from the _original attributes of the modified methods.
    """
    for api, method, _ in available_openai_apis_and_injectors():
        if hasattr(getattr(api, method), "_original"):
            setattr(api, method, getattr(getattr(api, method), "_original"))
