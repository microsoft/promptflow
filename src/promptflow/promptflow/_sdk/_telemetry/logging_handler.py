# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import functools
import logging
import os
import platform
import sys

from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
from azure.monitor.opentelemetry.exporter._constants import _APPLICATION_INSIGHTS_EVENT_MARKER_ATTRIBUTE
from azure.monitor.opentelemetry.exporter._generated.models import TelemetryItem
from opentelemetry.sdk._logs import LogData, LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.util.types import Attributes

from promptflow._sdk._configuration import Configuration

# promptflow-sdk in east us
INSTRUMENTATION_KEY = "8b52b368-4c91-4226-b7f7-be52822f0509"


def get_scrubbed_cloud_role():
    """Create cloud role for telemetry, will scrub user script name and only leave extension."""
    default = "Unknown Application"
    known_scripts = [
        "pfs",
        "pfutil.py",
        "pf",
        "pfazure",
        "pf.exe",
        "pfazure.exe",
        "app.py",
        "python -m unittest",
        "pytest",
        "gunicorn",
        "ipykernel_launcher.py",
        "jupyter-notebook",
        "jupyter-lab",
        "python",
        "_jb_pytest_runner.py",
        default,
    ]

    try:
        cloud_role = os.path.basename(sys.argv[0]) or default
        if cloud_role not in known_scripts:
            ext = os.path.splitext(cloud_role)[1]
            cloud_role = "***" + ext
    except Exception:
        # fallback to default cloud role if failed to scrub
        cloud_role = default
    return cloud_role


class PromptFlowSDKExporter(AzureMonitorLogExporter):
    def __init__(self, custom_dimensions, **kwargs):
        super().__init__(**kwargs)
        self._custom_dimensions = custom_dimensions

    def _log_to_envelope(self, log_data: LogData) -> TelemetryItem:
        log_data.log_record.attributes.update(self._custom_dimensions)
        envelope = super()._log_to_envelope(log_data=log_data)
        # scrub data before sending to appinsights
        role = get_scrubbed_cloud_role()
        envelope.tags["ai.cloud.role"] = role
        envelope.tags.pop("ai.cloud.roleInstance", None)
        envelope.tags.pop("ai.device.id", None)
        return envelope

    def _should_collect_stats(self):
        return False


# cspell:ignore AzureMLSDKLogHandler
class PromptFlowSDKLogHandler(LoggingHandler):
    """Customized AzureLogHandler for PromptFlow SDK"""

    def __init__(self, custom_dimensions, enable_telemetry):
        self._is_telemetry_enabled = enable_telemetry
        self.disable_telemetry_logger()
        exporter = PromptFlowSDKExporter(
            connection_string=f"InstrumentationKey={INSTRUMENTATION_KEY}",
            custom_dimensions=custom_dimensions,
        )
        logger_provider = LoggerProvider()
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        super().__init__(logger_provider=logger_provider)

    def emit(self, record: logging.LogRecord):
        # skip logging if telemetry is disabled
        if not self._is_telemetry_enabled:
            return

        try:
            super().emit(record)
            # log the record immediately if it is an error
            if record.exc_info and not all(item is None for item in record.exc_info):
                self.flush()
        except Exception:  # pylint: disable=broad-except
            # ignore any exceptions, telemetry collection errors shouldn't block an operation
            return

    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> Attributes:
        """Get the attributes from the log record.
        Since the value in Attributes cannot be dict,
        otherwise the dict value will be filtered out, so it is necessary to parse dic in this step.
        """
        from promptflow._utils.utils import is_in_ci_pipeline

        custom_dimensions = {
            "level": record.levelname,
            # add to distinguish if the log is from ci pipeline
            "from_ci": is_in_ci_pipeline(),
        }

        attributes = LoggingHandler._get_attributes(record)
        return {
            # Mark the data as CustomEvents and record the data to CustomEvents.
            _APPLICATION_INSIGHTS_EVENT_MARKER_ATTRIBUTE: True,
            **custom_dimensions,
            **attributes.get("custom_dimensions", {}),
        }

    @classmethod
    def disable_telemetry_logger(cls):
        """Disable opentelemetry's logging to avoid warning affect user experience"""

        from azure.monitor.opentelemetry.exporter.export.logs._exporter import _logger as exporter_logger
        from opentelemetry._logs._internal import _logger as provider_logger
        from opentelemetry.sdk._logs._internal import _logger as handler_logger
        from opentelemetry.sdk._logs._internal.export import _logger as processor_logger

        handler_logger.setLevel(logging.CRITICAL)
        processor_logger.setLevel(logging.CRITICAL)
        provider_logger.setLevel(logging.CRITICAL)
        exporter_logger.setLevel(logging.CRITICAL)


@functools.lru_cache()
def get_promptflow_sdk_log_handler():
    from promptflow._sdk._telemetry.telemetry import is_telemetry_enabled

    config = Configuration.get_instance()
    custom_dimensions = {
        "python_version": platform.python_version(),
        "installation_id": config.get_or_set_installation_id(),
    }

    handler = PromptFlowSDKLogHandler(
        custom_dimensions=custom_dimensions,
        enable_telemetry=is_telemetry_enabled(),
    )
    return handler


def get_appinsights_log_handler():
    """
    Enable the opentelemetry logging handler for specified logger and instrumentation key to send info to AppInsights.
    """

    try:
        return get_promptflow_sdk_log_handler()
    except Exception:  # pylint: disable=broad-except
        # ignore any exceptions, telemetry collection errors shouldn't block an operation
        return logging.NullHandler()
