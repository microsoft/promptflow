# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os
import platform
import sys

from opencensus.ext.azure.log_exporter import AzureEventHandler

from promptflow._sdk._configuration import Configuration

# promptflow-sdk in east us
INSTRUMENTATION_KEY = "8b52b368-4c91-4226-b7f7-be52822f0509"


# cspell:ignore overriden
def get_appinsights_log_handler():
    """
    Enable the OpenCensus logging handler for specified logger and instrumentation key to send info to AppInsights.
    """
    from promptflow._sdk._telemetry.telemetry import is_telemetry_enabled

    try:
        config = Configuration.get_instance()
        instrumentation_key = INSTRUMENTATION_KEY
        custom_properties = {
            "python_version": platform.python_version(),
            "installation_id": config.get_or_set_installation_id(),
        }

        handler = PromptFlowSDKLogHandler(
            connection_string=f"InstrumentationKey={instrumentation_key}",
            custom_properties=custom_properties,
            enable_telemetry=is_telemetry_enabled(),
        )
        return handler
    except Exception:  # pylint: disable=broad-except
        # ignore any exceptions, telemetry collection errors shouldn't block an operation
        return logging.NullHandler()


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


# cspell:ignore AzureMLSDKLogHandler
class PromptFlowSDKLogHandler(AzureEventHandler):
    """Customized AzureLogHandler for PromptFlow SDK"""

    def __init__(self, custom_properties, enable_telemetry, **kwargs):
        super().__init__(**kwargs)
        # disable AzureEventHandler's logging to avoid warning affect user experience
        self.disable_telemetry_logger()
        self._is_telemetry_enabled = enable_telemetry
        self._custom_dimensions = custom_properties

    def _check_stats_collection(self):
        # skip checking stats collection since it's time-consuming
        # according to doc: https://learn.microsoft.com/en-us/azure/azure-monitor/app/statsbeat
        # it doesn't affect customers' overall monitoring volume
        return False

    def emit(self, record):
        # skip logging if telemetry is disabled
        if not self._is_telemetry_enabled:
            return

        try:
            self._queue.put(record, block=False)

            # log the record immediately if it is an error
            if record.exc_info and not all(item is None for item in record.exc_info):
                self._queue.flush()
        except Exception:  # pylint: disable=broad-except
            # ignore any exceptions, telemetry collection errors shouldn't block an operation
            return

    def log_record_to_envelope(self, record):
        from promptflow._utils.utils import is_in_ci_pipeline

        # skip logging if telemetry is disabled

        if not self._is_telemetry_enabled:
            return
        custom_dimensions = {
            "level": record.levelname,
            # add to distinguish if the log is from ci pipeline
            "from_ci": is_in_ci_pipeline(),
        }
        custom_dimensions.update(self._custom_dimensions)
        if hasattr(record, "custom_dimensions") and isinstance(record.custom_dimensions, dict):
            record.custom_dimensions.update(custom_dimensions)
        else:
            record.custom_dimensions = custom_dimensions

        envelope = super().log_record_to_envelope(record=record)
        # scrub data before sending to appinsights
        role = get_scrubbed_cloud_role()
        envelope.tags["ai.cloud.role"] = role
        envelope.tags.pop("ai.cloud.roleInstance", None)
        envelope.tags.pop("ai.device.id", None)
        return envelope

    @classmethod
    def disable_telemetry_logger(cls):
        """Disable AzureEventHandler's logging to avoid warning affect user experience"""
        from opencensus.ext.azure.common.processor import logger as processor_logger
        from opencensus.ext.azure.common.storage import logger as storage_logger
        from opencensus.ext.azure.common.transport import logger as transport_logger

        processor_logger.setLevel(logging.CRITICAL)
        transport_logger.setLevel(logging.CRITICAL)
        storage_logger.setLevel(logging.CRITICAL)
