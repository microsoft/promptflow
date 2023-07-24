import logging
import pytest
import time
import uuid
from multiprocessing.pool import ThreadPool
from pathlib import Path
from tempfile import mkdtemp

from promptflow.utils.blob_utils import BlobStream
from promptflow.utils.logger_utils import (
    FileHandlerConcurrentWrapper,
    logger,
    flow_logger,
    update_log_path,
    FileHandler
)
from promptflow.utils.internal_logger_utils import SystemLogContext, TelemetryLogHandler, BlobFileHandler, FileType


class DummyException(Exception):
    pass


@pytest.mark.unittest
class TestSystemLogContext:
    def test_context_manager(self):
        log_handler = FileHandlerConcurrentWrapper()
        input_logger = logging.getLogger("test_setup_system_logger_context")
        input_logger.addHandler(log_handler)
        telemetry_log_handler = TelemetryLogHandler()
        input_logger.addHandler(telemetry_log_handler)

        log_path = str(Path(mkdtemp()) / "test.log")
        appinsights_connection_str = (
            f"InstrumentationKey={uuid.uuid4()};"
            "IngestionEndpoint=https://eastus-6.in.applicationinsights.azure.com/;"
            "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/")
        log_context = SystemLogContext(
            file_path=log_path,
            app_insights_instrumentation_key=appinsights_connection_str,
            custom_dimensions={"custom": "dimension"},
            file_type=FileType.Blob,
            input_logger=input_logger,
        )

        try:
            with log_context:
                # Make sure telemetry_log_handler is set.
                assert telemetry_log_handler._handler is not None
                # Make sure blob file handler is set.
                loggers = [logger, flow_logger, input_logger]
                for logger_ in loggers:
                    test_passed = False
                    for handler in logger_.handlers:
                        if isinstance(handler, FileHandlerConcurrentWrapper):
                            assert isinstance(log_handler.handler, BlobFileHandler)
                            test_passed = True

                assert test_passed
                logger.warning('Print %s', '&sig=signature')
                # Raise exception for test.
                raise DummyException('Raise exception for test.')
        except DummyException:
            pass

        # Make sure context variables are cleaned up.
        assert log_handler._context_var.get() is None


def _update_log_path(args):
    new_log_path, file_type = args
    log_path = "dummy-blob-uri"
    with SystemLogContext(file_path=log_path, file_type=file_type):
        time.sleep(1)
        update_log_path(new_log_path)
        time.sleep(1)
        for logger_ in [logger, flow_logger]:
            test_passed = False
            for wrapper in logger_.handlers:
                if isinstance(wrapper, FileHandlerConcurrentWrapper):
                    if file_type == FileType.Local:
                        assert isinstance(wrapper.handler, FileHandler)
                        assert isinstance(wrapper.handler._stream_handler, logging.FileHandler)
                    else:
                        assert isinstance(wrapper.handler, BlobFileHandler)
                        assert isinstance(wrapper.handler._stream_handler.stream, BlobStream)
                    test_passed = True
            assert test_passed


@pytest.mark.unittest
def test_update_log_path_thread_safe():
    file_types = [FileType.Local, FileType.Blob, FileType.Local]
    with ThreadPool(processes=3) as pool:
        results = pool.map(_update_log_path, [[f"path-{i}", file_types[i]] for i in range(3)])
        _ = list(results)
