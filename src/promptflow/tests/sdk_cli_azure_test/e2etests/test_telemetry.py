# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import os
import platform
import shutil
import sys
import tempfile
import uuid
from logging import Logger
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pydash
import pytest

from promptflow import load_run
from promptflow._constants import PF_USER_AGENT
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk._telemetry import (
    ActivityType,
    PromptFlowSDKLogHandler,
    get_appinsights_log_handler,
    get_telemetry_logger,
    is_telemetry_enabled,
    log_activity,
)
from promptflow._sdk._telemetry.logging_handler import get_promptflow_sdk_log_handler
from promptflow._sdk._utils import call_from_extension
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow._utils.utils import environment_variable_overwrite, parse_ua_to_dict
from promptflow.tracing._operation_context import OperationContext

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
FLOWS_DIR = "./tests/test_configs/flows"


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
            assert handler._is_telemetry_enabled is True

            get_promptflow_sdk_log_handler.cache_clear()
            handler = get_appinsights_log_handler()
            assert isinstance(handler, PromptFlowSDKLogHandler)
            assert handler._is_telemetry_enabled is False

    def test_call_from_extension(self):
        assert call_from_extension() is False
        with environment_variable_overwrite(PF_USER_AGENT, "prompt-flow-extension/1.0.0"):
            assert call_from_extension() is True
        # remove extension ua in context
        context = OperationContext().get_instance()
        context.user_agent = context.user_agent.replace("prompt-flow-extension/1.0.0", "")

    def test_custom_event(self, pf):
        from promptflow._sdk._configuration import Configuration
        from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKExporter

        envelope = None
        config = Configuration.get_instance()
        custom_dimensions = {
            "python_version": platform.python_version(),
            "installation_id": config.get_or_set_installation_id(),
        }
        log_to_envelope = PromptFlowSDKExporter(
            connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
            custom_dimensions=custom_dimensions,
        )._log_to_envelope

        def log_event(log_data):
            nonlocal envelope
            envelope = log_to_envelope(log_data)

        def check_evelope():
            logger = get_telemetry_logger()
            handler = logger.handlers[0]
            assert isinstance(handler, PromptFlowSDKLogHandler)
            custom_dimensions = pydash.get(envelope, "data.base_data.properties")
            assert isinstance(custom_dimensions, dict)
            # Note: need privacy review if we add new fields.
            if "start" in envelope.data.base_data.name:
                assert custom_dimensions.keys() == {
                    "request_id",
                    "activity_name",
                    "activity_type",
                    "subscription_id",
                    "resource_group_name",
                    "workspace_name",
                    "level",
                    "python_version",
                    "user_agent",
                    "installation_id",
                    "first_call",
                    "from_ci",
                    "error_category",
                    "error_type",
                    "error_target",
                    "error_message",
                    "error_detail",
                }
            elif "complete" in envelope.data.base_data.name:
                assert custom_dimensions.keys() == {
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
                    "first_call",
                    "from_ci",
                    "error_category",
                    "error_type",
                    "error_target",
                    "error_message",
                    "error_detail",
                }
            else:
                raise ValueError("Invalid message: {}".format(envelope.data.base_data.name))
            assert envelope.data.base_data.name.startswith("pfazure.runs.get")

        with patch.object(PromptFlowSDKExporter, "_log_to_envelope") as mock_logger, patch(
            "promptflow._sdk._telemetry.telemetry.get_telemetry_logger", side_effect=get_telemetry_logger
        ):
            mock_logger.side_effect = log_event
            try:
                pf.runs.get("not_exist")
            except RunNotFoundError:
                pass
            logger = get_telemetry_logger()
            logger.handlers[0].flush()
            check_evelope()

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
            assert ua_dict.keys() == {"promptflow-sdk"}

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
            user_agent = ClientUserAgentUtil.get_user_agent()
            ua_dict = parse_ua_to_dict(user_agent)
            assert ua_dict.keys() == {"promptflow-sdk"}

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
            user_agent = ClientUserAgentUtil.get_user_agent()
            ua_dict = parse_ua_to_dict(user_agent)
            assert ua_dict.keys() == {"promptflow-sdk"}

            # Call log_activity
            with log_activity(logger, "test_activity", activity_type=ActivityType.PUBLICAPI):
                # Perform some activity
                pass

        PFAzureClient(
            ml_client=pf._ml_client,
            subscription_id=pf._ml_client.subscription_id,
            resource_group_name=pf._ml_client.resource_group_name,
            workspace_name=pf._ml_client.workspace_name,
            user_agent="a/1.0.0",
        )
        user_agent = ClientUserAgentUtil.get_user_agent()
        ua_dict = parse_ua_to_dict(user_agent)
        assert ua_dict.keys() == {"promptflow-sdk", "a"}

        context = OperationContext().get_instance()
        context.user_agent = ""

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

    def test_scrub_fields(self):
        from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKExporter

        envelope = None
        log_to_envelope = PromptFlowSDKExporter(
            connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000", custom_dimensions={}
        )._log_to_envelope

        def log_event(log_data):
            nonlocal envelope
            envelope = log_to_envelope(log_data)

        def check_evelope():
            logger = get_telemetry_logger()
            handler = logger.handlers[0]
            assert isinstance(handler, PromptFlowSDKLogHandler)

            assert "message" == envelope.data.base_data.name
            assert "key" in envelope.data.base_data.properties
            assert "test" == envelope.data.base_data.properties["key"]

            # device name removed
            assert "ai.cloud.roleInstance" not in envelope.tags
            assert "ai.device.id" not in envelope.tags
            # role name should be scrubbed or kept in whitelist
            assert envelope.tags["ai.cloud.role"] in [os.path.basename(sys.argv[0]), "***"]

        with patch.object(PromptFlowSDKExporter, "_log_to_envelope") as mock_logger:
            mock_logger.side_effect = log_event
            logger = get_telemetry_logger()
            logger.info("message", extra={"custom_dimensions": {"key": "test"}})
            logger.handlers[0].flush()
            check_evelope()

    def test_different_event_for_node_run(self):
        from promptflow import PFClient

        pf = PFClient()

        from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKLogHandler

        def assert_node_run(*args, **kwargs):
            record = args[0]
            assert record.msg.startswith("pf.flows.node_test"), f"'pf.flows.node_test' not found in {record.msg!r}"
            assert (
                record.custom_dimensions["activity_name"] == "pf.flows.node_test"
            ), f"'pf.flows.node_test' not found in {record.custom_dimensions['activity_name']}"

        def assert_flow_test(*args, **kwargs):
            record = args[0]
            assert record.msg.startswith("pf.flows.test"), f"'pf.flows.test' not found in {record.msg!r}"
            assert (
                record.custom_dimensions["activity_name"] == "pf.flows.test"
            ), f"'pf.flows.test' not found in {record.custom_dimensions['activity_name']}"

        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree((Path(FLOWS_DIR) / "print_env_var").resolve().as_posix(), temp_dir, dirs_exist_ok=True)
            with patch.object(PromptFlowSDKLogHandler, "emit") as mock_logger:
                mock_logger.side_effect = assert_node_run

                pf.flows.test(temp_dir, node="print_env", inputs={"key": "API_BASE"})

            with patch.object(PromptFlowSDKLogHandler, "emit") as mock_logger:
                mock_logger.side_effect = assert_flow_test

                pf.flows.test(temp_dir, inputs={"key": "API_BASE"})

    @pytest.mark.skipif(
        condition=not is_live(), reason="Live mode can run successfully, but an error will be reported when recording."
    )
    def test_run_yaml_type(self, pf, randstr: Callable[[str], str]):
        from promptflow._constants import FlowType
        from promptflow._sdk._configuration import Configuration
        from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKExporter

        envelope = None
        flow_type = None
        config = Configuration.get_instance()
        custom_dimensions = {
            "python_version": platform.python_version(),
            "installation_id": config.get_or_set_installation_id(),
        }
        log_to_envelope = PromptFlowSDKExporter(
            connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
            custom_dimensions=custom_dimensions,
        )._log_to_envelope

        def log_event(log_data):
            nonlocal envelope
            envelope = log_to_envelope(log_data)

        def check_evelope():
            assert envelope.data.base_data.name.startswith("pfazure.runs.create_or_update")
            custom_dimensions = pydash.get(envelope, "data.base_data.properties")
            assert isinstance(custom_dimensions, dict)
            assert "flow_type" in custom_dimensions
            assert custom_dimensions["flow_type"] == flow_type

        with patch.object(PromptFlowSDKExporter, "_log_to_envelope", side_effect=log_event), patch(
            "promptflow._sdk._telemetry.telemetry.get_telemetry_logger", side_effect=get_telemetry_logger
        ):
            flow_type = FlowType.DAG_FLOW
            pf.run(
                flow="./tests/test_configs/flows/print_input_flow",
                data="./tests/test_configs/datas/print_input_flow.jsonl",
                name=randstr("name"),
            )
            logger = get_telemetry_logger()
            logger.handlers[0].flush()
            check_evelope()

            flow_type = FlowType.FLEX_FLOW
            pf.run(
                flow="./tests/test_configs/eager_flows/simple_with_req",
                data="./tests/test_configs/datas/simple_eager_flow_data.jsonl",
                name=randstr("name"),
            )
            logger.handlers[0].flush()
            check_evelope()
