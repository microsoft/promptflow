import asyncio
import functools

from promptflow._core.openai_injector import inject_function_async, inject_function_sync, inject_operation_headers

from .mock_tool import call_func, call_func_async


def inject_recording(f):
    if asyncio.iscoroutinefunction(f):

        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            return await call_func_async(f, args, kwargs)

    else:

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return call_func(f, args, kwargs)

    return wrapper


def inject_async_with_recording(f):
    wrapper_fun = inject_operation_headers(
        (inject_function_async(["api_key", "headers", "extra_headers"])(inject_recording(f)))
    )
    wrapper_fun._original = f
    return wrapper_fun


def inject_sync_with_recording(f):
    wrapper_fun = inject_operation_headers(
        (inject_function_sync(["api_key", "headers", "extra_headers"])(inject_recording(f)))
    )
    wrapper_fun._original = f
    return wrapper_fun
