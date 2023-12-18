# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging

from promptflow._sdk._configuration import Configuration

PROMPTFLOW_LOGGER_NAMESPACE = "promptflow._sdk._telemetry"


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


class WorkspaceTelemetryMixin(TelemetryMixin):
    def __init__(self, subscription_id, resource_group_name, workspace_name, **kwargs):
        # add telemetry to avoid conflict with subclass properties
        self._telemetry_subscription_id = subscription_id
        self._telemetry_resource_group_name = resource_group_name
        self._telemetry_workspace_name = workspace_name
        super().__init__(**kwargs)

    def _get_telemetry_values(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Return the telemetry values of run operations.

        :return: The telemetry values
        :rtype: Dict
        """
        return {
            "subscription_id": self._telemetry_subscription_id,
            "resource_group_name": self._telemetry_resource_group_name,
            "workspace_name": self._telemetry_workspace_name,
        }


def is_telemetry_enabled():
    """Check if telemetry is enabled. Telemetry is enabled by default.
    User can disable it by:
    1. running `pf config set telemetry.enabled=false` command.
    """
    config = Configuration.get_instance()
    telemetry_consent = config.get_telemetry_consent()
    if telemetry_consent is not None:
        return str(telemetry_consent).lower() == "true"
    return True


def get_telemetry_logger():
    from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKLogHandler, get_appinsights_log_handler

    current_logger = logging.getLogger(PROMPTFLOW_LOGGER_NAMESPACE)
    # avoid telemetry log appearing in higher level loggers
    current_logger.propagate = False
    current_logger.setLevel(logging.INFO)
    # check if current logger already has an appinsights handler to avoid logger handler duplication
    for log_handler in current_logger.handlers:
        if isinstance(log_handler, PromptFlowSDKLogHandler):
            # update existing handler's config
            log_handler._is_telemetry_enabled = is_telemetry_enabled()
            return current_logger
    # otherwise, remove the existing handler and create a new one
    for log_handler in current_logger.handlers:
        current_logger.removeHandler(log_handler)
    handler = get_appinsights_log_handler()
    current_logger.addHandler(handler)
    return current_logger
