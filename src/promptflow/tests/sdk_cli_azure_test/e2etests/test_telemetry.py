# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
from unittest.mock import patch

import pytest

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._utils import call_from_extension
from promptflow._telemetry.logging_handler import PromptFlowSDKLogHandler, get_appinsights_log_handler
from promptflow._utils.utils import environment_variable_overwrite


@contextlib.contextmanager
def cli_consent_config_overwrite(val):
    config = Configuration.get_instance()
    original_consent = config.get_telemetry_consent()
    config.set_telemetry_consent(val)
    try:
        yield
    finally:
        if original_consent:
            config.set_telemetry_consent(original_consent)
        else:
            config.set_telemetry_consent(False)


@pytest.mark.e2etest
class TestTelemetry:
    def test_logging_handler(self):
        # override environment variable
        with environment_variable_overwrite("TELEMETRY_ENABLED", "true"):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is True

        with environment_variable_overwrite("TELEMETRY_ENABLED", "false"):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is False

    def test_call_from_extension(self):
        assert call_from_extension() is False
        with environment_variable_overwrite("USER_AGENT", "prompt-flow-extension/1.0.0"):
            assert call_from_extension() is True

    def test_custom_event(self, pf):
        from opencensus.ext.azure.log_exporter import AzureEventHandler

        def log_event(*args, **kwargs):
            record = kwargs.get("record", None)
            assert record.custom_dimensions is not None
            assert isinstance(record.custom_dimensions, dict)
            assert record.custom_dimensions.keys() == {
                "request_id",
                "activity_name",
                "activity_type",
                "subscription_id",
                "resource_group_name",
                "workspace_name",
                "completion_status",
                "duration_ms",
                "level",
                "python_version",
                "user_agent",
                "installation_id",
            }
            assert record.msg.startswith("pfazure.runs.get")

        with patch.object(AzureEventHandler, "log_record_to_envelope") as mock_log:
            mock_log.side_effect = log_event
            with cli_consent_config_overwrite(True):
                try:
                    pf.runs.get("not_exist")
                except Exception:
                    pass
