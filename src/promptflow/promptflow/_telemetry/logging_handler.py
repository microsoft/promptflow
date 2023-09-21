# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import platform

from opencensus.ext.azure.common import utils
from opencensus.ext.azure.common.protocol import Data, Envelope, Message
from opencensus.ext.azure.log_exporter import AzureLogHandler

from promptflow._cli._configuration import Configuration
from promptflow._cli._user_agent import USER_AGENT

# b4ff2b60-2f72-4a5f-b7a6-571318b50ab2
# TODO: replace with prod app insights
INSTRUMENTATION_KEY = "b4ff2b60-2f72-4a5f-b7a6-571318b50ab2"


# cspell:ignore overriden
def get_appinsights_log_handler():
    """
    Enable the OpenCensus logging handler for specified logger and instrumentation key to send info to AppInsights.
    """
    from promptflow._telemetry.telemetry import is_telemetry_enabled

    try:
        instrumentation_key = INSTRUMENTATION_KEY
        config = Configuration.get_instance()
        custom_properties = {
            "python_version": platform.python_version(),
            "user_agent": USER_AGENT,
            "user_id": config.get_or_set_user_id(),
        }

        # TODO: use different instrumentation key for Europe
        handler = AzureMLSDKLogHandler(
            connection_string=f"InstrumentationKey={instrumentation_key}",
            custom_properties=custom_properties,
            enable_telemetry=is_telemetry_enabled(),
        )
        return handler
    except Exception:  # pylint: disable=broad-except
        # ignore any exceptions, telemetry collection errors shouldn't block an operation
        return logging.NullHandler()


# cspell:ignore AzureMLSDKLogHandler
class AzureMLSDKLogHandler(AzureLogHandler):
    """Customized AzureLogHandler for AzureML SDK"""

    def __init__(self, custom_properties, enable_telemetry, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._is_telemetry_collection_disabled = not enable_telemetry
        self._custom_properties = custom_properties

    def emit(self, record):
        if self._is_telemetry_collection_disabled:
            return

        try:
            self._queue.put(record, block=False)

            # log the record immediately if it is an error
            if record.exc_info and not all(item is None for item in record.exc_info):
                self._queue.flush()
        except Exception:  # pylint: disable=broad-except
            # ignore any exceptions, telemetry collection errors shouldn't block an operation
            return

    # The code below is vendored from opencensus-ext-azure's AzureLogHandler base class, but the telemetry disabling
    # logic has been added to the beginning. Without this, the base class would still send telemetry even if
    # enable_telemetry had been set to true.
    def log_record_to_envelope(self, record):
        if self._is_telemetry_collection_disabled:
            return None

        envelope = create_envelope(self.options.instrumentation_key, record)

        properties = {
            "process": record.processName,
            "module": record.module,
            "level": record.levelname,
        }
        properties.update(self._custom_properties)

        if hasattr(record, "properties") and isinstance(record.properties, dict):
            properties.update(record.properties)

        if not record.exc_info:
            envelope.name = "Microsoft.ApplicationInsights.Message"
            data = Message(
                message=self.format(record),
                severityLevel=max(0, record.levelno - 1) // 10,
                properties=properties,
            )
            envelope.data = Data(baseData=data, baseType="MessageData")
        return envelope


def create_envelope(instrumentation_key, record):
    envelope = Envelope(
        iKey=instrumentation_key,
        tags=dict(utils.azure_monitor_context),
        time=utils.timestamp_to_iso_str(record.created),
    )
    envelope.tags["ai.operation.id"] = getattr(
        record,
        "traceId",
        "00000000000000000000000000000000",
    )
    envelope.tags["ai.operation.parentId"] = "|{}.{}.".format(
        envelope.tags["ai.operation.id"],
        getattr(record, "spanId", "0000000000000000"),
    )

    return envelope
