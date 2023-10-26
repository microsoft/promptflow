# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import time
from unittest.mock import patch

import pytest

from promptflow._sdk._configuration import Configuration
from promptflow._sdk._utils import call_from_extension
from promptflow._telemetry.logging_handler import (
    EU_INSTRUMENTATION_KEY,
    PromptFlowSDKLogHandler,
    get_appinsights_log_handler,
)
from promptflow._utils.utils import environment_variable_overwrite

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD
from ..recording_utilities import is_live


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


@contextlib.contextmanager
def cli_eu_config_overwrite():
    config = Configuration.get_instance()
    config.set_config(Configuration.EU_USER, True)
    try:
        yield
    finally:
        config.set_config(Configuration.EU_USER, False)


@pytest.mark.skipif(condition=not is_live(), reason="telemetry tests, only run in live mode.")
@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
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
        from promptflow._core.operation_context import OperationContext

        assert call_from_extension() is False
        with environment_variable_overwrite("USER_AGENT", "prompt-flow-extension/1.0.0"):
            assert call_from_extension() is True
        # remove extension ua in context
        context = OperationContext().get_instance()
        context.user_agent = context.user_agent.replace("prompt-flow-extension/1.0.0", "")

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
            # sleep a while to make sure log thread can finish.
            time.sleep(20)

    def test_log_for_eu_user(self, pf):
        from opencensus.ext.azure.log_exporter import AzureEventHandler

        from promptflow._telemetry.telemetry import get_telemetry_logger

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
            with cli_consent_config_overwrite(True), cli_eu_config_overwrite():
                try:
                    pf.runs.get("not_exist")
                except Exception:
                    pass
                # the logging handler should use eu instrumentation key
                logger = get_telemetry_logger()
                handler = logger.handlers[0]
                assert isinstance(handler, PromptFlowSDKLogHandler)
                assert handler.options.instrumentation_key == EU_INSTRUMENTATION_KEY
            # sleep a while to make sure log thread can finish.
            time.sleep(20)
