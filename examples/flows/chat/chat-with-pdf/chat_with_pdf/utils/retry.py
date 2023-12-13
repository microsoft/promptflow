from typing import Tuple, Union, Optional, Type
import functools
import time
import random


def retry_and_handle_exceptions(
    exception_to_check: Union[Type[Exception], Tuple[Type[Exception], ...]],
    max_retries: int = 3,
    initial_delay: float = 1,
    exponential_base: float = 2,
    jitter: bool = False,
    extract_delay_from_error_message: Optional[any] = None,
):
    def deco_retry(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exception_to_check as e:
                    if i == max_retries - 1:
                        raise Exception(
                            "Func execution failed after {0} retries: {1}".format(
                                max_retries, e
                            )
                        )
                    delay *= exponential_base * (1 + jitter * random.random())
                    delay_from_error_message = None
                    if extract_delay_from_error_message is not None:
                        delay_from_error_message = extract_delay_from_error_message(
                            str(e)
                        )
                    final_delay = (
                        delay_from_error_message if delay_from_error_message else delay
                    )
                    print(
                        "Func execution failed. Retrying in {0} seconds: {1}".format(
                            final_delay, e
                        )
                    )
                    time.sleep(final_delay)

        return wrapper

    return deco_retry


def retry_and_handle_exceptions_for_generator(
    exception_to_check: Union[Type[Exception], Tuple[Type[Exception], ...]],
    max_retries: int = 3,
    initial_delay: float = 1,
    exponential_base: float = 2,
    jitter: bool = False,
    extract_delay_from_error_message: Optional[any] = None,
):
    def deco_retry(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    for value in func(*args, **kwargs):
                        yield value
                    break
                except exception_to_check as e:
                    if i == max_retries - 1:
                        raise Exception(
                            "Func execution failed after {0} retries: {1}".format(
                                max_retries, e
                            )
                        )
                    delay *= exponential_base * (1 + jitter * random.random())
                    delay_from_error_message = None
                    if extract_delay_from_error_message is not None:
                        delay_from_error_message = extract_delay_from_error_message(
                            str(e)
                        )
                    final_delay = (
                        delay_from_error_message if delay_from_error_message else delay
                    )
                    print(
                        "Func execution failed. Retrying in {0} seconds: {1}".format(
                            final_delay, e
                        )
                    )
                    time.sleep(final_delay)

        return wrapper

    return deco_retry
