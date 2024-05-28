# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import time
from functools import wraps
from typing import Tuple, Type, Union

from requests import Response

from promptflow._utils.logger_utils import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


def retry(exception_to_check: Union[Type[Exception], Tuple[Type[Exception], ...]], tries=4, delay=3, backoff=2):
    """
    From https://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/

    Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param exception_to_check: the exception to check. may be a tuple of
        exceptions to check
    :type exception_to_check: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: log the retry action if specified
    :type logger: logging.Logger
    """

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            retry_times, delay_seconds = tries, delay
            while retry_times > 1:
                try:
                    logger.debug("Running %s, %d more tries to go.", str(f), retry_times)
                    return f(*args, **kwargs)
                except exception_to_check:
                    time.sleep(delay_seconds)
                    retry_times -= 1
                    delay_seconds *= backoff
                    logger.warning("%s, Retrying in %d seconds...", str(exception_to_check), delay_seconds)
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


HTTP_SAFE_CODES = set(range(506)) - {408, 429, 500, 502, 503, 504}
HTTP_RETRY_CODES = set(range(999)) - HTTP_SAFE_CODES


def http_retry_wrapper(f, tries=4, delay=3, backoff=2):
    """
    :param f: function to be retried, should return a Response object.
    :type f: Callable
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    """

    @wraps(f)
    def f_retry(*args, **kwargs):
        retry_times, delay_seconds = tries, delay
        while retry_times > 1:
            result = f(*args, **kwargs)
            if not isinstance(result, Response):
                logger.debug(f"Not a retryable function, expected return type {Response}, got {type(result)}.")
                return result
            if result.status_code not in HTTP_RETRY_CODES:
                return result
            logger.warning(
                f"Retryable error code {result.status_code} returned, retrying in {delay_seconds} seconds. "
                f"Function {f.__name__}, Reason: {result.reason}"
            )
            time.sleep(delay_seconds)
            retry_times -= 1
            delay_seconds *= backoff
        return f(*args, **kwargs)

    return f_retry


def async_retry(exception_to_check: Union[Exception, Tuple[Exception]], tries=4, delay=3, backoff=2, _logger=None):
    """
    Retry calling the decorated async function using an exponential backoff.

    :param exception_to_check: the exception to check. may be a tuple of exceptions to check
    :type exception_to_check: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay each retry
    :type backoff: int
    :param _logger: log the retry action if specified
    :type _logger: logging.Logger
    """

    def deco_retry(f):
        @wraps(f)
        async def f_retry(*args, **kwargs):
            retry_times, delay_seconds = tries, delay
            while retry_times > 1:
                try:
                    return await f(*args, **kwargs)
                except exception_to_check as e:
                    if _logger:
                        message = f"{str(e)}. Retrying in {delay_seconds} seconds..."
                        _logger.warning(message)
                    await asyncio.sleep(delay_seconds)
                    retry_times -= 1
                    delay_seconds *= backoff
            return await f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry
