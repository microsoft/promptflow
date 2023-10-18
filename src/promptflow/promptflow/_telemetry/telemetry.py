# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os

from promptflow._sdk._configuration import Configuration
from promptflow._telemetry.logging_handler import PromptFlowSDKLogHandler, get_appinsights_log_handler

TELEMETRY_ENABLED = "TELEMETRY_ENABLED"
PROMPTFLOW_LOGGER_NAMESPACE = "promptflow._telemetry"


class TelemetryMixin(object):
    def __init__(self, **kwargs):
        # Need to call init for potential parent, otherwise it won't be initialized.
        super().__init__(**kwargs)

    def _get_telemetry_values(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Return the telemetry values of object.

        :return: The telemetry values
        :rtype: Dict
        """
        return {}


def is_telemetry_enabled():
    """Check if telemetry is enabled. User can enable telemetry by
    1. setting environment variable TELEMETRY_ENABLED to true.
    2. running `pf config set cli.telemetry_enabled=true` command.
    If None of the above is set, telemetry is disabled by default.
    """
    telemetry_enabled = os.getenv(TELEMETRY_ENABLED)
    if telemetry_enabled is not None:
        return str(telemetry_enabled).lower() == "true"
    config = Configuration.get_instance()
    telemetry_consent = config.get_telemetry_consent()
    if telemetry_consent is not None:
        return telemetry_consent
    return False


def get_telemetry_logger():
    current_logger = logging.getLogger(PROMPTFLOW_LOGGER_NAMESPACE)
    # avoid telemetry log appearing in higher level loggers
    current_logger.propagate = False
    current_logger.setLevel(logging.INFO)
    # check if current logger already has an appinsights handler to avoid logger handler duplication
    for log_handler in current_logger.handlers:
        if isinstance(log_handler, PromptFlowSDKLogHandler):
            return current_logger
    handler = get_appinsights_log_handler()
    current_logger.addHandler(handler)
    return current_logger
