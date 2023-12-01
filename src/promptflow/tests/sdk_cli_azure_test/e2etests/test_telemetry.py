# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import time
import uuid
from logging import Logger
from typing import Callable
from unittest.mock import MagicMock, patch

import pydash
import pytest

from promptflow import load_run, PFClient
from promptflow._constants import PF_USER_AGENT
from promptflow._sdk._user_agent import USER_AGENT as SDK_USER_AGENT
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._utils import call_from_extension
from promptflow._telemetry.activity import ActivityType, log_activity
from promptflow._telemetry.logging_handler import PromptFlowSDKLogHandler, get_appinsights_log_handler
from promptflow._telemetry.telemetry import get_telemetry_logger, is_telemetry_enabled
from promptflow._utils.utils import environment_variable_overwrite, parse_ua_to_dict

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


RUNS_DIR = "./tests/test_configs/runs"


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.usefixtures("mock_set_headers_with_user_aml_token", "single_worker_thread_pool", "vcr_recording")
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

    def test_inner_function_call(self, pf, runtime: str, randstr: Callable[[str], str]):
        request_ids = set()
        first_sdk_calls = []

        def check_inner_call(*args, **kwargs):
            if "extra" in kwargs:
                request_id = pydash.get(kwargs, "extra.custom_dimensions.request_id")
                first_sdk_call = pydash.get(kwargs, "extra.custom_dimensions.first_call")
                request_ids.add(request_id)
                first_sdk_calls.append(first_sdk_call)

        with patch.object(Logger, "info") as mock_logger:
            mock_logger.side_effect = check_inner_call
            run = load_run(
                source=f"{RUNS_DIR}/run_with_env.yaml",
                params_override=[{"runtime": runtime}],
            )
            run.name = randstr("name")
            pf.runs.create_or_update(run=run)

        # only 1 request id
        assert len(request_ids) == 1
        # only 1 and last call is public call
        assert first_sdk_calls[0] is True
        assert first_sdk_calls[-1] is True
        assert set(first_sdk_calls[1:-1]) == {False}

    def test_different_request_id(self):
        from promptflow import PFClient

        pf = PFClient()
        request_ids = set()
        first_sdk_calls = []

        def check_inner_call(*args, **kwargs):
            if "extra" in kwargs:
                request_id = pydash.get(kwargs, "extra.custom_dimensions.request_id")
                first_sdk_call = pydash.get(kwargs, "extra.custom_dimensions.first_call")
                request_ids.add(request_id)
                first_sdk_calls.append(first_sdk_call)

        with patch.object(Logger, "info") as mock_logger:
            mock_logger.side_effect = check_inner_call
            run = load_run(
                source=f"{RUNS_DIR}/run_with_env.yaml",
            )
            # create 2 times will get 2 request ids
            run.name = str(uuid.uuid4())
            pf.runs.create_or_update(run=run)
            run.name = str(uuid.uuid4())
            pf.runs.create_or_update(run=run)

        # only 1 request id
        assert len(request_ids) == 2
        # 1 and last call is public call
        assert first_sdk_calls[0] is True
        assert first_sdk_calls[-1] is True

    def test_duplicate_ua(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')

        try:
            ua1 = 'ua1 ua2 ua3'
            context['user_agent'] = ua1  # Add fixed UA
            origin_agent = context.get_user_agent()

            ua2 = '    ua3   ua2  ua1'
            context.append_user_agent(ua2)  # Env configuration ua with extra spaces, duplicate ua.
            agent = context.get_user_agent()
            assert agent == origin_agent + ' ' + ua2

            ua3 = '  ua3   ua2 ua1  ua4  '
            context.append_user_agent(ua3)  # Env modifies ua with extra spaces, duplicate ua except ua4.
            agent = context.get_user_agent()
            assert agent == origin_agent + ' ' + ua2 + ' ' + ua3

            ua4 = 'ua1 ua2'  #
            context.append_user_agent(ua4)  # Env modifies ua with extra spaces, duplicate ua but not be added.
            agent = context.get_user_agent()
            assert agent == origin_agent + ' ' + ua2 + ' ' + ua3

            ua5 = 'ua2 ua4 ua5    '
            context.append_user_agent(ua5)  # Env modifies ua with extra spaces, duplicate ua except ua5.
            agent = context.get_user_agent()
            assert agent == origin_agent + ' ' + ua2 + ' ' + ua3 + ' ' + ua5
        except Exception as e:
            raise e
        finally:
            context['user_agent'] = default_ua

    def test_extra_spaces_ua(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')

        try:
            origin_agent = context.get_user_agent()
            ua1 = '    ua1   ua2   ua3    '
            context['user_agent'] = ua1
            assert context.get_user_agent() == origin_agent + ' ' + ua1

            ua2 = 'ua4      ua5      ua6      '
            context.append_user_agent(ua2)
            assert context.get_user_agent() == origin_agent + ' ' + ua1 + ' ' + ua2
        except Exception as e:
            raise e
        finally:
            context['user_agent'] = default_ua

    def test_ua_covered(self):
        context = OperationContext.get_instance()
        default_ua = context.get('user_agent', '')
        try:
            PFClient()
            assert SDK_USER_AGENT in context.get_user_agent()

            context["user_agent"] = 'test_agent'
            assert SDK_USER_AGENT not in context.get_user_agent()
        except Exception as e:
            raise
        finally:
            context['user_agent'] = default_ua