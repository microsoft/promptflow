# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import platform
import traceback

from opencensus.ext.azure.common import utils
from opencensus.ext.azure.common.protocol import Data, Envelope, ExceptionData, Message
from opencensus.ext.azure.log_exporter import AzureLogHandler

# b4ff2b60-2f72-4a5f-b7a6-571318b50ab2
# TODO: replace with prod app insights
INSTRUMENTATION_KEY = "b4ff2b60-2f72-4a5f-b7a6-571318b50ab2"
PROMPTFLOW_LOGGER_NAMESPACE = "promptflow._telemetry"


class CustomDimensionsFilter(logging.Filter):
    """Add application-wide properties to AzureLogHandler records"""

    def __init__(self, custom_dimensions=None):  # pylint: disable=super-init-not-called
        self.custom_dimensions = custom_dimensions or {}

    def filter(self, record: dict) -> bool:
        """Adds the default custom_dimensions into the current log record. Does not
        otherwise filter any records

        :param record: The record
        :type record: dict
        :return: True
        :rtype: bool
        """

        custom_dimensions = self.custom_dimensions.copy()
        custom_dimensions.update(getattr(record, "custom_dimensions", {}))
        record.custom_dimensions = custom_dimensions

        return True


# cspell:ignore overriden
def get_appinsights_log_handler(
    user_agent,
    *args,  # pylint: disable=unused-argument
    instrumentation_key=None,
    component_name=None,
    enable_telemetry=True,
    **kwargs,
):
    """Enable the OpenCensus logging handler for specified logger and instrumentation key to send info to AppInsights.

    :param user_agent: Information about the user's browser.
    :type user_agent: Dict[str, str]
    :param args: Optional arguments for formatting messages.
    :type args: list
    :keyword instrumentation_key: The Application Insights instrumentation key.
    :paramtype instrumentation_key: str
    :keyword component_name: The component name.
    :paramtype component_name: str
    :keyword enable_telemetry: Whether to enable telemetry. Will be overriden to False if not in a Jupyter Notebook.
    :paramtype enable_telemetry: bool
    :keyword kwargs: Optional keyword arguments for adding additional information to messages.
    :paramtype kwargs: dict
    :return: The logging handler.
    :rtype: AzureMLSDKLogHandler
    """
    try:
        if instrumentation_key is None:
            instrumentation_key = INSTRUMENTATION_KEY

        child_namespace = component_name or __name__
        current_logger = logging.getLogger(PROMPTFLOW_LOGGER_NAMESPACE).getChild(child_namespace)
        current_logger.propagate = False
        current_logger.setLevel(logging.CRITICAL)

        custom_properties = {"PythonVersion": platform.python_version()}
        custom_properties.update({"user_agent": user_agent})
        if "properties" in kwargs:
            custom_properties.update(kwargs.pop("properties"))
        handler = AzureMLSDKLogHandler(
            connection_string=f"InstrumentationKey={instrumentation_key}",
            custom_properties=custom_properties,
            enable_telemetry=enable_telemetry,
        )
        current_logger.addHandler(handler)

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
        self.addFilter(CustomDimensionsFilter(self._custom_properties))

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
        if hasattr(record, "custom_dimensions") and isinstance(record.custom_dimensions, dict):
            properties.update(record.custom_dimensions)

        if record.exc_info:
            exctype, _value, tb = record.exc_info
            callstack = []
            level = 0
            has_full_stack = False
            exc_type = "N/A"
            message = self.format(record)
            if tb is not None:
                has_full_stack = True
                for _, line, method, _text in traceback.extract_tb(tb):
                    callstack.append(
                        {
                            "level": level,
                            "method": method,
                            "line": line,
                        }
                    )
                    level += 1
                callstack.reverse()
            elif record.message:
                message = record.message

            if exctype is not None:
                exc_type = exctype.__name__

            envelope.name = "Microsoft.ApplicationInsights.Exception"

            data = ExceptionData(
                exceptions=[
                    {
                        "id": 1,
                        "outerId": 0,
                        "typeName": exc_type,
                        "message": message,
                        "hasFullStack": has_full_stack,
                        "parsedStack": callstack,
                    }
                ],
                severityLevel=max(0, record.levelno - 1) // 10,
                properties=properties,
            )
            envelope.data = Data(baseData=data, baseType="ExceptionData")
        else:
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
