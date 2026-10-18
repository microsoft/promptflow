# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from unittest.mock import MagicMock, patch

import pytest
from azure.monitor.opentelemetry.exporter._constants import _APPLICATION_INSIGHTS_EVENT_MARKER_ATTRIBUTE
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, ReadableLogRecord
from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor

from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKExporter, PromptFlowSDKLogHandler


@pytest.mark.unittest
class TestTelemetryLogging:
    def test_exporter_log_to_envelope(self):
        custom_dimensions = {"test_dim": "test_val", "python_version": "3.11"}
        exporter = PromptFlowSDKExporter(
            connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
            custom_dimensions=custom_dimensions,
        )

        provider = LoggerProvider()
        in_memory_exporter = InMemoryLogExporter()
        provider.add_log_record_processor(SimpleLogRecordProcessor(in_memory_exporter))
        handler = LoggingHandler(logger_provider=provider)

        logger = logging.getLogger("test_telemetry_exporter")
        logger.addHandler(handler)
        logger.warning("test message", extra={"custom_dimensions": {"extra_key": "extra_val"}})

        finished_logs = in_memory_exporter.get_finished_logs()
        assert len(finished_logs) == 1
        record = finished_logs[0]
        assert isinstance(record, ReadableLogRecord)

        envelope = exporter._log_to_envelope(record)
        assert envelope is not None
        assert "ai.cloud.role" in envelope.tags
        assert "ai.cloud.roleInstance" not in envelope.tags
        assert "ai.device.id" not in envelope.tags
        props = envelope.data.base_data.properties
        assert props["test_dim"] == "test_val"

    def test_positional_delegation_to_super(self):
        exporter = PromptFlowSDKExporter(
            connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
            custom_dimensions={"key": "val"},
        )
        provider = LoggerProvider()
        in_memory_exporter = InMemoryLogExporter()
        provider.add_log_record_processor(SimpleLogRecordProcessor(in_memory_exporter))
        handler = LoggingHandler(logger_provider=provider)
        logger = logging.getLogger("test_positional")
        logger.addHandler(handler)
        logger.info("info msg")

        record = in_memory_exporter.get_finished_logs()[0]
        assert isinstance(record, ReadableLogRecord)

        with patch("azure.monitor.opentelemetry.exporter.AzureMonitorLogExporter._log_to_envelope") as mock_super:
            mock_envelope = MagicMock()
            mock_envelope.tags = {}
            mock_super.return_value = mock_envelope

            exporter._log_to_envelope(record)

            mock_super.assert_called_once_with(record)

    def test_log_handler_disable_telemetry_logger(self):
        PromptFlowSDKLogHandler.disable_telemetry_logger()

    def test_log_handler_emit_disabled(self):
        handler = PromptFlowSDKLogHandler(custom_dimensions={}, enable_telemetry=False)
        record = logging.LogRecord("test", logging.INFO, "path", 1, "msg", (), None)
        with patch.object(LoggingHandler, "emit") as mock_super_emit:
            handler.emit(record)
            mock_super_emit.assert_not_called()

    def test_log_handler_emit_enabled(self):
        handler = PromptFlowSDKLogHandler(custom_dimensions={}, enable_telemetry=True)
        record = logging.LogRecord("test", logging.INFO, "path", 1, "msg", (), None)
        with patch.object(LoggingHandler, "emit") as mock_super_emit:
            handler.emit(record)
            mock_super_emit.assert_called_once_with(record)

    def test_log_handler_get_attributes(self):
        record = logging.LogRecord("test", logging.WARNING, "path", 1, "msg", (), None)
        record.custom_dimensions = {"custom_k": "custom_v"}
        attrs = PromptFlowSDKLogHandler._get_attributes(record)
        assert attrs[_APPLICATION_INSIGHTS_EVENT_MARKER_ATTRIBUTE] is True
        assert attrs["level"] == "WARNING"
        assert attrs["custom_k"] == "custom_v"
