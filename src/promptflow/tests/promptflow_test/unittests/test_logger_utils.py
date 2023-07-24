import pytest
import io
import logging
import time
from pathlib import Path
from multiprocessing.pool import ThreadPool
from tempfile import mkdtemp
from uuid import uuid4

from promptflow.utils.credential_scrubber import CredentialScrubber
from promptflow.utils.logger_utils import (
    CredentialScrubberFormatter,
    FileHandler,
    FileHandlerConcurrentWrapper,
    LogContext,
)


def _set_handler(
        logger: logging.Logger,
        handler: FileHandler,
        log_content: str):

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
                _set_handler,
                ((logger, FileHandler(log_path_list[i]), f"log {i}") for i in range(process_num)))
            results = list(results)

        # Make sure log content is as expected.
        for i, log_path in enumerate(log_path_list):
            with open(log_path, 'r') as f:
                log = f.read()
                log_lines = log.split('\n')
                assert len(log_lines) == 2
                assert f"log {i}" in log_lines[0]
                assert log_lines[1] == ''


@pytest.mark.unittest
class TestCredentialScrubberFormatter:
    def test_log(self, logger, stream_handler):
        """Make sure credentials by logger.log are scrubbed."""
        formatter = CredentialScrubberFormatter(scrub_customer_content=False)
        formatter.set_credential_list(['dummy secret'])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        logger.info('testinfo&sig=signature')
        logger.error('testerror&key=accountkey')
        logger.warning('testwarning&sig=signature')
        logger.critical('print dummy secret')
        expected_log_output = (
            f'testinfo&sig={CredentialScrubber.PLACE_HOLDER}\n'
            f'testerror&key={CredentialScrubber.PLACE_HOLDER}\n'
            f'testwarning&sig={CredentialScrubber.PLACE_HOLDER}\n'
            f'print {CredentialScrubber.PLACE_HOLDER}\n')
        assert stream_handler.stream.getvalue() == expected_log_output

    def test_log_with_args(self, logger, stream_handler):
        """Make sure credentials by logger.log (in args) are scrubbed."""
        formatter = CredentialScrubberFormatter(scrub_customer_content=False)
        formatter.set_credential_list(['dummy secret'])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.info('testinfo&sig=%s credential=%s', 'signature', 'dummy secret')
        expected_log_output = (f'testinfo&sig={CredentialScrubber.PLACE_HOLDER} '
                               f'credential={CredentialScrubber.PLACE_HOLDER}\n')
        assert stream_handler.stream.getvalue() == expected_log_output

    def test_log_with_exc_info(self, logger, stream_handler):
        """Make sure credentials in exception are scrubbed."""
        formatter = CredentialScrubberFormatter(scrub_customer_content=False)
        formatter.set_credential_list(['dummy secret'])
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        exception = DummyException('credential=dummy secret accountkey=accountkey')
        logger.exception('test exception', exc_info=exception)
        expected_log_output = 'credential=**data_scrubbed** accountkey=**data_scrubbed**'
        assert expected_log_output in stream_handler.stream.getvalue()

    def test_log_with_customer_content(self, logger, stream_handler):
        """Make sure customer content is scrubbed if necessary."""
        formatter = CredentialScrubberFormatter(scrub_customer_content=True)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.info('User name = {customer_content}', extra={'customer_content': 'test_user'})
        assert f'User name = {CredentialScrubber.PLACE_HOLDER}' in stream_handler.stream.getvalue()

    def test_log_exception_with_customer_content(self, logger, stream_handler):
        formatter = CredentialScrubberFormatter(scrub_customer_content=True)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        exception = DummyException("Test dummy exception")
        try:
            raise exception
        except DummyException as e:
            logger.exception(f"Exception: {str(e)}")
        expect_log = ("Exception: Test dummy exception\n"
                      "Exception type: <class 'promptflow_test.unittests.test_logger_utils.DummyException'>\n")
        assert stream_handler.stream.getvalue() == expect_log

    def test_log_with_traceback(self, logger, stream_handler):
        formatter = CredentialScrubberFormatter(scrub_customer_content=True)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.info("Test log. Traceback: (this is traceback)\nFile")
        expect_log = f"Test log. Traceback{CredentialScrubber.PLACE_HOLDER}\n"
        assert stream_handler.stream.getvalue() == expect_log

    def test_set_credential_list_thread_safe(self):
        formatter = CredentialScrubberFormatter(scrub_customer_content=False)

        def set_and_check_credential_list(credential_list):
            formatter.set_credential_list(credential_list)
            time.sleep(1)
            assert formatter.credential_scrubber.custom_str_set == set(credential_list)

        with ThreadPool(processes=3) as pool:
            results = pool.map(set_and_check_credential_list, [[f'secret {i}', f'credential {i}'] for i in range(3)])
            _ = list(results)


@pytest.mark.unittest
class TestLogContext:
    def test_context_manager(self):
        log_handler = FileHandlerConcurrentWrapper()
        logger = logging.getLogger('test_setup_logger_context')
        logger.addHandler(log_handler)

        log_path = str(Path(mkdtemp()) / 'test.log')
        try:
            with LogContext(log_path, input_logger=logger):
                # Make sure context variables are set.
                inner_handler = log_handler._context_var.get()
                assert isinstance(inner_handler, FileHandler)
                assert isinstance(inner_handler._formatter, CredentialScrubberFormatter)
                scrubber = inner_handler._formatter._context_var.get()
                assert scrubber is not None
                logger.warning('Print %s', '&sig=signature')
                # Raise exception for test.
                raise DummyException('Raise exception for test.')
        except DummyException:
            pass

        # Make sure log content is as expected.
        with open(log_path, 'r') as f:
            log_content = f.read()
        assert f'Print &sig={CredentialScrubber.PLACE_HOLDER}' in log_content

        # Make sure context variables are cleaned up.
        assert log_handler._context_var.get() is None
