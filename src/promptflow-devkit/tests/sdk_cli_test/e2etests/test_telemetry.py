# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import platform
from unittest.mock import patch

import pydash
import pytest

from promptflow._sdk._telemetry import get_telemetry_logger


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestTelemetry:
    def test_run_yaml_type(self, pf):
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
            assert envelope.data.base_data.name.startswith("pf.runs.create_or_update")
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
            )
            logger = get_telemetry_logger()
            logger.handlers[0].flush()
            check_evelope()

            flow_type = FlowType.FLEX_FLOW
            pf.run(
                flow="./tests/test_configs/eager_flows/simple_with_req",
                data="./tests/test_configs/datas/simple_eager_flow_data.jsonl",
            )
            logger.handlers[0].flush()
            check_evelope()

    def test_flow_type_with_pfazure_flows(self, pf):
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
            assert envelope.data.base_data.name.startswith("pf.flows.test")
            custom_dimensions = pydash.get(envelope, "data.base_data.properties")
            assert isinstance(custom_dimensions, dict)
            assert "flow_type" in custom_dimensions
            assert custom_dimensions["flow_type"] == flow_type

        with patch.object(PromptFlowSDKExporter, "_log_to_envelope", side_effect=log_event), patch(
            "promptflow._sdk._telemetry.telemetry.get_telemetry_logger", side_effect=get_telemetry_logger
        ):
            flow_type = FlowType.DAG_FLOW
            try:
                pf.flows.test(flow="./tests/test_configs/flows/print_input_flow")
            except Exception:
                pass
            logger = get_telemetry_logger()
            logger.handlers[0].flush()
            check_evelope()

            flow_type = FlowType.FLEX_FLOW
            try:
                pf.flows.test(flow="./tests/test_configs/eager_flows/simple_with_req")
            except Exception:
                pass
            logger.handlers[0].flush()
            check_evelope()
