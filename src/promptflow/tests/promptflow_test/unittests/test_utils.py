from io import StringIO
from logging import Logger, StreamHandler
from multiprocessing.pool import ThreadPool

import pytest

from promptflow.utils.utils import count_and_log_progress


@pytest.mark.unittest
def test_count_and_log_progress():
    s = StringIO()
    logger = Logger("test-logger")
    logger.addHandler(StreamHandler(s))
    total_count = 23
    with ThreadPool(processes=3) as pool:
        results_gen = count_and_log_progress(
            inputs=pool.imap_unordered(lambda i: i, ([1] * total_count)),
            logger=logger,
            total_count=total_count,
        )
        _ = sorted(results_gen)

    for i in range(2, total_count, 2):
        assert f"{i} / 23 finished." in s.getvalue()
    assert "23 / 23 finished." in s.getvalue()
