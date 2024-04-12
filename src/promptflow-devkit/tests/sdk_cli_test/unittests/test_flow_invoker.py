# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._load_functions import load_flow
from promptflow.core._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow.core._serving.flow_invoker import FlowInvoker
from promptflow.exceptions import UserErrorException

FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
EXAMPLE_FLOW_DIR = FLOWS_DIR / "web_classification"
EXAMPLE_FLOW_FILE = EXAMPLE_FLOW_DIR / "flow.dag.yaml"
EXAMPLE_FLOW = load_flow(EXAMPLE_FLOW_FILE)


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestFlowInvoker:
    # Note: e2e test of flow invoker has been covered by test_flow_serve.
    def test_flow_invoker_unsupported_connection_provider(self):
        with pytest.raises(UnsupportedConnectionProvider):
            FlowInvoker(flow=EXAMPLE_FLOW, connection_provider=[])

        with pytest.raises(UserErrorException):
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider="Unsupported connection provider",
            )

    def test_flow_invoker_custom_connection_provider(self):
        # Return is not a list
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider=lambda: {},
            )
        assert "should return a list of connections" in str(e.value)

        # Return is not connection type
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(
                flow=EXAMPLE_FLOW,
                connection_provider=lambda: [1, 2],
            )
        assert "should be connection type" in str(e.value)
