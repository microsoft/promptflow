import functools
import inspect
from datetime import datetime

import openai

from promptflow.contracts.trace import Trace, TraceType

from .tracer import Tracer


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
                Tracer.pop(result)
            return result

        return wrapped_method

    return wrapper


def inject_operation_headers(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        from promptflow.core.operation_context import OperationContext

        # Inject headers from operation context, overwrite injected header with headers from kwargs.
        injected_headers = OperationContext.get_instance().get_http_headers()
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
    """This function modifies the create methods of the OpenAI API classes
    to inject logic before calling the original methods.
    It stores the original methods as _original attributes of the create methods.
    """
    for openai_api in available_openai_apis():
        # Check if the create method of the openai_api class has already been modified
        if not hasattr(openai_api.create, "_original"):
            # If not, modify it by calling the inject function with it as an argument
            openai_api.create = inject(openai_api.create)


def recover_openai_api():
    """This function restores the original create methods of the OpenAI API classes
    by assigning them back from the _original attributes of the modified methods.
    """
    for openai_api in available_openai_apis():
        # Check if the create method of the openai_api class has been modified
        if hasattr(openai_api.create, "_original"):
            # If yes, restore it by assigning it back from the _original attribute of the modified method
            openai_api.create = getattr(openai_api.create, "_original")
