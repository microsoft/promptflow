import io
import logging
import time
from multiprocessing.pool import ThreadPool
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import Mock
from uuid import uuid4

import pytest

from promptflow._utils.credential_scrubber import CredentialScrubber
from promptflow._utils.logger_utils import (
    CredentialScrubberFormatter,
    FileHandler,
    FileHandlerConcurrentWrapper,
    LogContext,
    bulk_logger,
    scrub_credentials,
    update_log_path,
)
from promptflow.contracts.run_mode import RunMode

from ...utils import load_content


def _set_handler(logger: logging.Logger, handler: FileHandler, log_content: str):
    for h in logger.handlers:
        if isinstance(h, FileHandlerConcurrentWrapper):
            h.handler = handler

    time.sleep(1)
    logger.warning(log_content)
    h.clear()


class DummyException(Exception):
    pass


@pytest.fixture
def logger():
    logger = logging.getLogger(str(uuid4()))
    logger.setLevel(logging.INFO)
    return logger


@pytest.fixture
def stream_handler():
    stream = io.StringIO()
    return logging.StreamHandler(stream)


@pytest.mark.unittest
class TestFileHandlerConcurrentWrapper:
    def test_set_handler_thread_safe(self):
        wrapper = FileHandlerConcurrentWrapper()
        logger = logging.getLogger("test execution log handler")
        logger.addHandler(wrapper)

        process_num = 3
        folder_path = Path(mkdtemp())
        log_path_list = [str(folder_path / f"log_{i}.log") for i in range(process_num)]

        with ThreadPool(processes=process_num) as pool:
            results = pool.starmap(
                _set_handler, ((logger, FileHandler(log_path_list[i]), f"log {i}") for i in range(process_num))
            )
            results = list(results)

        # Make sure log content is as expected.
        for i, log_path in enumerate(log_path_list):
            with open(log_path, "r") as f:
                log = f.read()
                log_lines = log.split("\n")
                assert len(log_lines) == 2
                assert f"log {i}" in log_lines[0]
                assert log_lines[1] == ""

    def test_clear(self):
        wrapper = FileHandlerConcurrentWrapper()
        assert wrapper.handler is None

        log_path = str(Path(mkdtemp()) / "logs.log")
        file_handler = FileHandler(log_path)
        file_handler.close = Mock(side_effect=Exception("test exception"))
        wrapper.handler = file_handler

        wrapper.clear()
        assert wrapper.handler is None


@pytest.mark.unittest
class TestCredentialScrubberFormatter:
    def test_log(self, logger, stream_handler):
        """Make sure credentials by logger.log are scrubbed."""
        formatter = CredentialScrubberFormatter()
        formatter.set_credential_list(["dummy secret"])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        logger.info("testinfo&sig=signature")
        logger.error("testerror&key=accountkey")
        logger.warning("testwarning&sig=signature")
        logger.critical("print dummy secret")
        expected_log_output = (
            f"testinfo&sig={CredentialScrubber.PLACE_HOLDER}\n"
            f"testerror&key={CredentialScrubber.PLACE_HOLDER}\n"
            f"testwarning&sig={CredentialScrubber.PLACE_HOLDER}\n"
            f"print {CredentialScrubber.PLACE_HOLDER}\n"
        )
        assert stream_handler.stream.getvalue() == expected_log_output

    def test_log_with_args(self, logger, stream_handler):
        """Make sure credentials by logger.log (in args) are scrubbed."""
        formatter = CredentialScrubberFormatter()
        formatter.set_credential_list(["dummy secret"])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.info("testinfo&sig=%s credential=%s", "signature", "dummy secret")
        expected_log_output = (
            f"testinfo&sig={CredentialScrubber.PLACE_HOLDER} " f"credential={CredentialScrubber.PLACE_HOLDER}\n"
        )
        assert stream_handler.stream.getvalue() == expected_log_output

    def test_log_with_exc_info(self, logger, stream_handler):
        """Make sure credentials in exception are scrubbed."""
        formatter = CredentialScrubberFormatter()
        formatter.set_credential_list(["dummy secret"])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        exception = DummyException("credential=dummy secret accountkey=accountkey")
        logger.exception("test exception", exc_info=exception)
        expected_log_output = "credential=**data_scrubbed** accountkey=**data_scrubbed**"
        assert expected_log_output in stream_handler.stream.getvalue()

    def test_set_credential_list_thread_safe(self):
        formatter = CredentialScrubberFormatter()

        def set_and_check_credential_list(credential_list):
            formatter.set_credential_list(credential_list)
            time.sleep(1)
            assert formatter.credential_scrubber.custom_str_set == set(credential_list)

        with ThreadPool(processes=3) as pool:
            results = pool.map(set_and_check_credential_list, [[f"secret {i}", f"credential {i}"] for i in range(3)])
            _ = list(results)


@pytest.mark.unittest
class TestLogContext:
    def test_context_manager(self):
        log_handler = FileHandlerConcurrentWrapper()
        logger = logging.getLogger("test_setup_logger_context")
        logger.addHandler(log_handler)

        log_path = str(Path(mkdtemp()) / "test.log")
        try:
            log_context_initializer = LogContext(log_path).get_initializer()
            log_context = log_context_initializer()
            log_context.input_logger = logger
            assert LogContext.get_current() is None
            with log_context:
                assert LogContext.get_current() is not None
                # Make sure context variables are set.
                inner_handler = log_handler._context_var.get()
                assert isinstance(inner_handler, FileHandler)
                assert isinstance(inner_handler._formatter, CredentialScrubberFormatter)
                scrubber = inner_handler._formatter._context_var.get()
                assert scrubber is not None
                logger.warning("Print %s", "&sig=signature")
                # Raise exception for test.
                raise DummyException("Raise exception for test.")
        except DummyException:
            pass

        # Make sure log content is as expected.
        with open(log_path, "r") as f:
            log_content = f.read()
        assert f"Print &sig={CredentialScrubber.PLACE_HOLDER}" in log_content

        # Make sure context variables are cleaned up.
        assert log_handler._context_var.get() is None

    def test_update_log_path(self):
        log_handler = FileHandlerConcurrentWrapper()
        input_logger = logging.getLogger("input_logger")
        input_logger.addHandler(log_handler)

        folder_path = Path(mkdtemp())
        original_log_path = str(folder_path / "original_log.log")
        with LogContext(original_log_path, input_logger=input_logger, run_mode=RunMode.Batch):
            bulk_logger.info("test log")
            input_logger.warning("test input log")
            original_log = load_content(original_log_path)
            keywords = ["test log", "test input log", "execution.bulk", "input_logger", "INFO", "WARNING"]
            assert all(keyword in original_log for keyword in keywords)

            # Update log path
            log_path = str(folder_path / "log_without_input_logger.log")
            update_log_path(log_path, input_logger)
            bulk_logger.info("test update log")
            input_logger.warning("test update input log")
            log = load_content(log_path)
            keywords = ["test update log", "test update input log", "execution.bulk", "input_logger", "INFO", "WARNING"]
            assert all(keyword in log for keyword in keywords)

    def test_scrub_credentials(self):
        log_content = "sig=signature&key=accountkey"
        folder_path = Path(mkdtemp())
        logs_path = str(folder_path / "logs.log")
        scrubbed_log_content = scrub_credentials(log_content)
        assert scrubbed_log_content == "sig=**data_scrubbed**&key=**data_scrubbed**"
        with LogContext(logs_path):
            scrubbed_log_content = scrub_credentials(log_content)
            assert scrubbed_log_content == "sig=**data_scrubbed**&key=**data_scrubbed**"
