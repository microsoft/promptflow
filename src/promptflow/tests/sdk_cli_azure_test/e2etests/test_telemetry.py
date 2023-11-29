# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import os
import time
from unittest.mock import MagicMock, patch

import pydash
import pytest

from promptflow._constants import PF_USER_AGENT
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._utils import call_from_extension
from promptflow._telemetry.activity import ActivityType, log_activity
from promptflow._telemetry.logging_handler import PromptFlowSDKLogHandler, get_appinsights_log_handler
from promptflow._telemetry.telemetry import get_telemetry_logger, is_telemetry_enabled
from promptflow._utils.utils import environment_variable_overwrite, parse_ua_to_dict
from promptflow._constants import USER_AGENT

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


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
            config.set_telemetry_consent(True)


@contextlib.contextmanager
def extension_consent_config_overwrite(val):
    config = Configuration.get_instance()
    original_consent = config.get_config(key=Configuration.EXTENSION_COLLECT_TELEMETRY)
    config.set_config(key=Configuration.EXTENSION_COLLECT_TELEMETRY, value=val)
    try:
        yield
    finally:
        if original_consent:
            config.set_config(key=Configuration.EXTENSION_COLLECT_TELEMETRY, value=original_consent)
        else:
            config.set_config(key=Configuration.EXTENSION_COLLECT_TELEMETRY, value=True)


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.usefixtures("single_worker_thread_pool", "vcr_recording")
@pytest.mark.e2etest
class TestTelemetry:
    def test_logging_handler(self):
        # override environment variable
        with cli_consent_config_overwrite(True):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is True

        with cli_consent_config_overwrite(False):
            handler = get_appinsights_log_handler()
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is False

    def test_call_from_extension(self):
        from promptflow._core.operation_context import OperationContext

        assert call_from_extension() is False
        with environment_variable_overwrite(PF_USER_AGENT, "prompt-flow-extension/1.0.0"):
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
            try:
                pf.runs.get("not_exist")
            except Exception:
                pass
            logger = get_telemetry_logger()
            handler = logger.handlers[0]
            assert isinstance(handler, PromptFlowSDKLogHandler)
            # sleep a while to make sure log thread can finish.
            time.sleep(20)

    def test_default_logging_behavior(self):
        assert is_telemetry_enabled() is True
        # default enable telemetry
        logger = get_telemetry_logger()
        handler = logger.handlers[0]
        assert isinstance(handler, PromptFlowSDKLogHandler)
        assert handler._is_telemetry_enabled is True

    def test_close_logging_handler(self):
        with cli_consent_config_overwrite(False):
            logger = get_telemetry_logger()
            handler = logger.handlers[0]
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is False

        with extension_consent_config_overwrite(False):
            with environment_variable_overwrite(PF_USER_AGENT, "prompt-flow-extension/1.0.0"):
                logger = get_telemetry_logger()
                handler = logger.handlers[0]
                assert isinstance(handler, PromptFlowSDKLogHandler)
                assert handler._is_telemetry_enabled is False

        # default enable telemetry
        logger = get_telemetry_logger()
        handler = logger.handlers[0]
        assert isinstance(handler, PromptFlowSDKLogHandler)
        assert handler._is_telemetry_enabled is True

    def test_cached_logging_handler(self):
        # should get same logger & handler instance if called multiple times
        logger = get_telemetry_logger()
        handler = next((h for h in logger.handlers if isinstance(h, PromptFlowSDKLogHandler)), None)
        another_logger = get_telemetry_logger()
        another_handler = next((h for h in another_logger.handlers if isinstance(h, PromptFlowSDKLogHandler)), None)
        assert logger is another_logger
        assert handler is another_handler

    def test_sdk_telemetry_ua(self, pf):
        from promptflow import PFClient
        from promptflow.azure import PFClient as PFAzureClient

        # log activity will pick correct ua
        def assert_ua(*args, **kwargs):
            ua = pydash.get(kwargs, "extra.custom_dimensions.user_agent", None)
            ua_dict = parse_ua_to_dict(ua)
            assert ua_dict.keys() == {"promptflow-sdk", "promptflow"}

        logger = MagicMock()
        logger.info = MagicMock()
        logger.info.side_effect = assert_ua

        # clear user agent before test
        context = OperationContext().get_instance()
        context.user_agent = ""
        # get telemetry logger from SDK should not have extension ua
        # start a clean local SDK client
        with environment_variable_overwrite(PF_USER_AGENT, ""):
            PFClient()
            user_agent = context.get_user_agent()
            ua_dict = parse_ua_to_dict(user_agent)
            assert ua_dict.keys() == {"promptflow-sdk", "promptflow"}

            # Call log_activity
            with log_activity(logger, "test_activity", activity_type=ActivityType.PUBLICAPI):
                # Perform some activity
                pass

        # start a clean Azure SDK client
        with environment_variable_overwrite(PF_USER_AGENT, ""):
            PFAzureClient(
                ml_client=pf._ml_client,
                subscription_id=pf._ml_client.subscription_id,
                resource_group_name=pf._ml_client.resource_group_name,
                workspace_name=pf._ml_client.workspace_name,
            )
            user_agent = context.get_user_agent()
            ua_dict = parse_ua_to_dict(user_agent)
            assert ua_dict.keys() == {"promptflow-sdk", "promptflow"}

            # Call log_activity
            with log_activity(logger, "test_activity", activity_type=ActivityType.PUBLICAPI):
                # Perform some activity
                pass

    def test_ci_user_agent(self) -> None:
        os.environ[USER_AGENT] = "perf_monitor/1.0"
        context = OperationContext.get_instance()
        assert "perf_monitor/1.0" in context.get_user_agent()
