import functools
import time
import typing


def sqlite_timer(operation: str):
    def decorator(func: typing.Callable) -> typing.Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            ret = func(*args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"operation[{operation}] duration_ms: {duration_ms}")
            return ret
        return wrapper
    return decorator
