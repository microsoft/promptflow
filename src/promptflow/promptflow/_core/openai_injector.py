# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import functools
import inspect
import os
from datetime import datetime

import openai

from promptflow._core.operation_context import OperationContext
from promptflow.contracts.trace import Trace, TraceType

from .tracer import Tracer

USER_AGENT_HEADER = "x-ms-useragent"
PROMPTFLOW_PREFIX = "ms-azure-ai-promptflow-"


def inject_function(args_to_ignore=None, trace_type=TraceType.LLM):
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
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # Inject headers from operation context, overwrite injected header with headers from kwargs.
        injected_headers = get_aoai_telemetry_headers()
        original_headers = kwargs.get("headers")
        if original_headers and isinstance(original_headers, dict):
            injected_headers.update(original_headers)
        kwargs.update(headers=injected_headers)

        return f(*args, **kwargs)

    return wrapper


def inject(f):
    wrapper_fun = inject_operation_headers((inject_function(["api_key", "headers"])(f)))
    wrapper_fun._original = f
    return wrapper_fun


def available_openai_apis():
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


def inject_openai_api():
    """This function:
    1. Modifies the create methods of the OpenAI API classes to inject logic before calling the original methods.
    It stores the original methods as _original attributes of the create methods.
    2. Updates the openai api configs from environment variables.
    """
    for openai_api in available_openai_apis():
        # Check if the create method of the openai_api class has already been modified
        if not hasattr(openai_api.create, "_original"):
            # If not, modify it by calling the inject function with it as an argument
            openai_api.create = inject(openai_api.create)

    # The openai package reads api configs from environment variables only at import time.
    # So we need to update the openai api configs from environment variables here.
    # Please refer to this issue: https://github.com/openai/openai-python/issues/557.
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
    for openai_api in available_openai_apis():
        # Check if the create method of the openai_api class has been modified
        if hasattr(openai_api.create, "_original"):
            # If yes, restore it by assigning it back from the _original attribute of the modified method
            openai_api.create = getattr(openai_api.create, "_original")
