# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time
from functools import partial, wraps
from typing import Tuple, Union

from sqlalchemy.exc import OperationalError


def retry(exception_to_check: Union[Exception, Tuple[Exception]], tries=4, delay=3, backoff=2, logger=None):
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
                    if logger:
                        logger.info("Running %s, %d more tries to go.", str(f), retry_times)
                    return f(*args, **kwargs)
                except exception_to_check:
                    time.sleep(delay_seconds)
                    retry_times -= 1
                    delay_seconds *= backoff
                    if logger:
                        logger.warning("%s, Retrying in %d seconds...", str(exception_to_check), delay_seconds)
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


sqlite_retry = partial(retry, exception_to_check=OperationalError, tries=10, delay=0.5, backoff=1)()
