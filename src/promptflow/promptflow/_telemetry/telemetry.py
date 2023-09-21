# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os

from promptflow._cli._configuration import Configuration
from promptflow._telemetry.logging_handler import get_appinsights_log_handler

TELEMETRY_ENABLED = "TELEMETRY_ENABLED"
PROMPTFLOW_LOGGER_NAMESPACE = "promptflow._telemetry"


def is_telemetry_enabled():
    """Check if telemetry is enabled. User can enable telemetry by
    1. setting environment variable TELEMETRY_ENABLED to true.
    2. running `pf config set cli.telemetry_enable=true` command.
    If None of the above is set, will prompt an input to ask user to enable telemetry.
    """
    telemetry_enabled = os.getenv(TELEMETRY_ENABLED)
    if telemetry_enabled is not None:
        return str(telemetry_enabled).lower() == "true"
    config = Configuration.get_instance()
    telemetry_consent = config.get_telemetry_consent()
    if telemetry_consent is not None:
        return telemetry_consent


def get_telemetry_logger():
    current_logger = logging.getLogger(PROMPTFLOW_LOGGER_NAMESPACE)
    # avoid telemetry log appearing in higher level loggers
    current_logger.propagate = False
    current_logger.setLevel(logging.INFO)
    handler = get_appinsights_log_handler()
    current_logger.addHandler(handler)
    return current_logger
