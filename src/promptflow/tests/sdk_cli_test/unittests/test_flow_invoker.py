# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow.core import Flow
from promptflow.core._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow.core._serving.flow_invoker import FlowInvoker
from promptflow.exceptions import UserErrorException

PROMOTFLOW_ROOT = Path(__file__).parent.parent.parent.parent
FLOWS_DIR = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")
EXAMPLE_FLOW_DIR = FLOWS_DIR / "web_classification"
EXAMPLE_FLOW_FILE = EXAMPLE_FLOW_DIR / "flow.dag.yaml"
EXAMPLE_FLOW = Flow.load(EXAMPLE_FLOW_DIR)._init_executable()


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestFlowInvoker:
    # Note: e2e test of flow invoker has been covered by test_flow_serve.
    def test_flow_invoker_unsupported_connection_provider(self):
        with pytest.raises(UnsupportedConnectionProvider):
            FlowInvoker(
                flow=EXAMPLE_FLOW, connection_provider=[], flow_path=EXAMPLE_FLOW_FILE, working_dir=EXAMPLE_FLOW_DIR
            )

        with pytest.raises(UserErrorException):
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider="unsupported",
                flow_path=EXAMPLE_FLOW_FILE,
                working_dir=EXAMPLE_FLOW_DIR,
            )

    def test_flow_invoker_custom_connection_provider(self):
        # Return is not a list
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider=lambda: {},
                flow_path=EXAMPLE_FLOW_FILE,
                working_dir=EXAMPLE_FLOW_DIR,
            )
        assert "should return a list of connections" in str(e.value)

        # Return is not connection type
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider=lambda: [1, 2],
                flow_path=EXAMPLE_FLOW_FILE,
                working_dir=EXAMPLE_FLOW_DIR,
            )
        assert "should be connection type" in str(e.value)
