import logging
import sys
import time
from multiprocessing.pool import ThreadPool

import pytest
from dateutil.parser import parse

from promptflow._core.log_manager import NodeLogManager, NodeLogWriter

RUN_ID = "dummy_run_id"
NODE_NAME = "dummy_node"
LINE_NUMBER = 1


def assert_print_result(i: int, run_logger: NodeLogWriter):
    run_id = f"{RUN_ID}-{i}"
    run_logger.set_node_info(run_id, NODE_NAME, LINE_NUMBER)
    time.sleep(i / 10)
    print(i)
    assert_datetime_prefix(run_logger.get_log(run_id), str(i) + "\n")


def is_datetime(string: str) -> bool:
    """Check if a string follows datetime format."""
    try:
        parse(string)
        return True

    except ValueError:
        return False


def assert_datetime_prefix(string: str, expected_str: str):
    """Assert if string has a datetime prefix, such as:
    [2023-04-17T07:49:54+0000] example string
    """
    datetime_prefix = string[string.index("[") + 1 : string.index("]")]
    inner_str = string[string.index("]") + 2 :]
    assert is_datetime(datetime_prefix)
    assert inner_str == expected_str


@pytest.mark.unittest
class TestNodeLogManager:
    def test_get_logs(self):
        with NodeLogManager(record_datetime=False) as lm:
            lm.set_node_context(RUN_ID, NODE_NAME, LINE_NUMBER)
            print("test")
            print("test2")
            print("test stderr", file=sys.stderr)
            assert lm.get_logs(RUN_ID).get("stdout") == "test\ntest2\n"
            assert lm.get_logs(RUN_ID).get("stderr") == "test stderr\n"
            lm.clear_node_context(RUN_ID)
            assert lm.get_logs(RUN_ID).get("stdout") is None
            assert lm.get_logs(RUN_ID).get("stderr") is None

    def test_logging(self):
        with NodeLogManager(record_datetime=False) as lm:
            lm.set_node_context(RUN_ID, NODE_NAME, LINE_NUMBER)
            stdout_logger = logging.getLogger("stdout")
            stderr_logger = logging.getLogger("stderr")
            stdout_logger.addHandler(logging.StreamHandler(stream=sys.stdout))
            stderr_logger.addHandler(logging.StreamHandler(stream=sys.stderr))
            stdout_logger.warning("test stdout")
            stderr_logger.warning("test stderr")
            logs = lm.get_logs(RUN_ID)
            assert logs.get("stdout") == "test stdout\n"
            assert logs.get("stderr") == "test stderr\n"

    def test_exit_context_manager(self):
        with NodeLogManager() as lm:
            assert lm.stdout_logger is sys.stdout
        assert lm.stdout_logger != sys.stdout

    def test_datetime_prefix(self):
        with NodeLogManager(record_datetime=True) as lm:
            lm.set_node_context(RUN_ID, NODE_NAME, LINE_NUMBER)
            print("test")
            print("test2")
            output = lm.get_logs(RUN_ID).get("stdout")
            outputs = output.split("\n")
            assert_datetime_prefix(outputs[0], "test")
            assert_datetime_prefix(outputs[1], "test2")
            assert outputs[2] == ""


@pytest.mark.unittest
class TestNodeLogWriter:
    def test_set_node_info(self):
        run_logger = NodeLogWriter(sys.stdout)
        assert run_logger.get_log(RUN_ID) is None
        run_logger.set_node_info(RUN_ID, NODE_NAME, LINE_NUMBER)
        assert run_logger.get_log(RUN_ID) == ""

    def test_clear_node_info(self):
        run_logger = NodeLogWriter(sys.stdout)
        run_logger.clear_node_info(RUN_ID)
        run_logger.set_node_info(RUN_ID, NODE_NAME, LINE_NUMBER)
        run_logger.clear_node_info(RUN_ID)
        assert run_logger.run_id_to_stdout.get(RUN_ID) is None

    def test_get_log(self):
        run_logger = NodeLogWriter(sys.stdout)
        sys.stdout = run_logger
        print("test")
        assert run_logger.get_log(RUN_ID) is None
        run_logger.set_node_info(RUN_ID, NODE_NAME, LINE_NUMBER)
        print("test")
        assert_datetime_prefix(run_logger.get_log(RUN_ID), "test\n")
        run_logger.clear_node_info(RUN_ID)
        assert run_logger.get_log(RUN_ID) is None

    def test_multi_thread(self):
        run_logger = NodeLogWriter(sys.stdout)
        sys.stdout = run_logger
        with ThreadPool(processes=10) as pool:
            results = pool.starmap(assert_print_result, ((i, run_logger) for i in range(10)))
            for r in results:
                pass
