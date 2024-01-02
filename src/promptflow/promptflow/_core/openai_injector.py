# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import functools
import inspect
import os
from datetime import datetime
from importlib.metadata import version

import openai

from promptflow._core.operation_context import OperationContext
from promptflow.contracts.trace import Trace, TraceType

from .tracer import Tracer

USER_AGENT_HEADER = "x-ms-useragent"
PROMPTFLOW_PREFIX = "ms-azure-ai-promptflow-"
IS_LEGACY_OPENAI = version("openai").startswith("0.")


def inject_function_async(args_to_ignore=None, trace_type=TraceType.LLM):
    args_to_ignore = args_to_ignore or []
    args_to_ignore = set(args_to_ignore)

    def wrapper(f):
        sig = inspect.signature(f).parameters

        @functools.wraps(f)
        async def wrapped_method(*args, **kwargs):
            if not Tracer.active():
                return await f(*args, **kwargs)

            all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
            for key in args_to_ignore:
                all_kwargs.pop(key, None)
            name = f.__qualname__ if not f.__module__ else f.__module__ + "." + f.__qualname__
            trace = Trace(
                name=name,
                type=trace_type,
                inputs=all_kwargs,
                start_time=datetime.utcnow().timestamp(),
            )
            Tracer.push(trace)
            try:
                result = await f(*args, **kwargs)
            except Exception as ex:
                Tracer.pop(error=ex)
                raise
            else:
                result = Tracer.pop(result)
            return result

        return wrapped_method

    return wrapper


def inject_function_sync(args_to_ignore=None, trace_type=TraceType.LLM):
    args_to_ignore = args_to_ignore or []
    args_to_ignore = set(args_to_ignore)

    def wrapper(f):
        sig = inspect.signature(f).parameters

        @functools.wraps(f)
        def wrapped_method(*args, **kwargs):
            if not Tracer.active():
                return f(*args, **kwargs)

            all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
            for key in args_to_ignore:
                all_kwargs.pop(key, None)
            name = f.__qualname__ if not f.__module__ else f.__module__ + "." + f.__qualname__
            trace = Trace(
                name=name,
                type=trace_type,
                inputs=all_kwargs,
                start_time=datetime.utcnow().timestamp(),
            )
            Tracer.push(trace)
            try:
                result = f(*args, **kwargs)
            except Exception as ex:
                Tracer.pop(error=ex)
                raise
            else:
                result = Tracer.pop(result)
            return result

        return wrapped_method

    return wrapper


def get_aoai_telemetry_headers() -> dict:
    """Get the http headers for AOAI request.

    The header, whose name starts with "ms-azure-ai-" or "x-ms-", is used to track the request in AOAI. The
    value in this dict will be recorded as telemetry, so please do not put any sensitive information in it.

    Returns:
        A dictionary of http headers.
    """
    # get promptflow info from operation context
    operation_context = OperationContext.get_instance()
    context_info = operation_context.get_context_dict()
    promptflow_info = {k.replace("_", "-"): v for k, v in context_info.items()}

    # init headers
    headers = {USER_AGENT_HEADER: operation_context.get_user_agent()}

    # update header with promptflow info
    headers.update({f"{PROMPTFLOW_PREFIX}{k}": str(v) if v is not None else "" for k, v in promptflow_info.items()})

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


def available_openai_apis_async():
    if IS_LEGACY_OPENAI:
        for api in ("Completion", "ChatCompletion", "Embedding"):
            try:
                openai_api = getattr(openai, api)
                if hasattr(openai_api, "acreate"):
                    yield openai_api
            except AttributeError:
                # This is expected for older versions of openai or unsupported APIs.
                # E.g. ChatCompletion API was introduced in 2023 and requires openai>=0.27.0 to work.
                # Older versions of openai do not have this API and will raise an AttributeError if we try to use it.
                pass
    else:
        for api in ("AsyncCompletions", "AsyncChat", "AsyncEmbeddings"):
            try:
                if api == "AsyncChat":
                    openai_api = getattr(openai.resources.chat, "AsyncCompletions")
                else:
                    openai_api = getattr(openai.resources, api)
                if hasattr(openai_api, "create"):
                    yield openai_api
            except Exception:
                # To avoid breaking changes included in future upgrades, we ignore all exceptions here.
                pass


def available_openai_apis_sync():
    if IS_LEGACY_OPENAI:
        for api in ("Completion", "ChatCompletion", "Embedding"):
            try:
                openai_api = getattr(openai, api)
                if hasattr(openai_api, "create"):
                    yield openai_api
            except AttributeError:
                # This is expected for older versions of openai or unsupported APIs.
                # E.g. ChatCompletion API was introduced in 2023 and requires openai>=0.27.0 to work.
                # Older versions of openai do not have this API and will raise an AttributeError if we try to use it.
                pass
    else:
        for api in ("Completions", "Chat", "Embeddings"):
            try:
                if api == "Chat":
                    openai_api = getattr(openai.resources.chat, "Completions")
                else:
                    openai_api = getattr(openai.resources, api)
                if hasattr(openai_api, "create"):
                    yield openai_api
            except Exception:
                # To avoid breaking changes included in future upgrades, we ignore all exceptions here.
                pass


def inject_openai_api():
    """This function:
    1. Modifies the create methods of the OpenAI API classes to inject logic before calling the original methods.
    It stores the original methods as _original attributes of the create methods.
    2. Updates the openai api configs from environment variables.
    """
    for openai_api_sync in available_openai_apis_sync():
        # Check if the create method of the openai_api class has already been modified
        if hasattr(openai_api_sync, "create") and not hasattr(openai_api_sync.create, "_original"):
            # If not, modify it by calling the inject function with it as an argument
            openai_api_sync.create = inject_sync(openai_api_sync.create)

    for openai_api_async in available_openai_apis_async():
        # Due to the issue reported in https://github.com/openai/openai-python/issues/996,
        # Async interface was not recognized as a coroutine by inspect.iscoroutinefunction.
        # This means that async injection needs to be handled differently to ensure decorators
        # behave correctly for asynchronous methods.

        # Check if the create method of the openai_api class has already been modified
        if hasattr(openai_api_async, "create") and not hasattr(openai_api_async.create, "_original"):
            # If not, modify it by calling the inject function with it as an argument
            openai_api_async.create = inject_async(openai_api_async.create)

    if IS_LEGACY_OPENAI:
        for openai_api_async in available_openai_apis_async():
            # Check if the acreate method of the openai_api class has already been modified
            if hasattr(openai_api_async, "acreate") and not hasattr(openai_api_async.acreate, "_original"):
                # If not, modify it by calling the inject function with it as an argument
                openai_api_async.acreate = inject_async(openai_api_async.acreate)

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
    recover_openai_api_sync()
    recover_openai_api_async()


def recover_openai_api_sync():
    """This function restores the original create methods of the OpenAI API classes
    by assigning them back from the _original attributes of the modified methods.
    """
    for openai_api_sync in available_openai_apis_sync():
        # Check if the create method of the openai_api class has been modified
        if hasattr(openai_api_sync.create, "_original"):
            # If yes, restore it by assigning it back from the _original attribute of the modified method
            openai_api_sync.create = getattr(openai_api_sync.create, "_original")


def recover_openai_api_async():
    """This function restores the original create methods of the OpenAI API classes
    by assigning them back from the _original attributes of the modified methods.
    """
    for openai_api_async in available_openai_apis_async():
        # Check if the create method of the openai_api class has been modified
        if hasattr(openai_api_async, "acreate") and hasattr(openai_api_async.acreate, "_original"):
            # If yes, restore it by assigning it back from the _original attribute of the modified method
            openai_api_async.acreate = getattr(openai_api_async.acreate, "_original")

        if hasattr(openai_api_async, "create") and hasattr(openai_api_async.create, "_original"):
            # If yes, restore it by assigning it back from the _original attribute of the modified method
            openai_api_async.create = getattr(openai_api_async.create, "_original")
