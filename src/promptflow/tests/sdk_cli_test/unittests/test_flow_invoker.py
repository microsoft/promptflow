# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow._sdk._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow._sdk._serving.flow_invoker import FlowInvoker

PROMOTFLOW_ROOT = Path(__file__).parent.parent.parent.parent
FLOWS_DIR = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")
EXAMPLE_FLOW = FLOWS_DIR / "web_classification"


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestFlowInvoker:
    # Note: e2e test of flow invoker has been covered by test_flow_serve.
    def test_flow_invoker_unsupported_connection_provider(self):
        with pytest.raises(UnsupportedConnectionProvider):
            FlowInvoker(flow=EXAMPLE_FLOW, connection_provider=[])

        with pytest.raises(ValueError):
            FlowInvoker(flow=EXAMPLE_FLOW, connection_provider="unsupported")

    def test_flow_invoker_custom_connection_provider(self):
        # Return is not a list
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(flow=EXAMPLE_FLOW, connection_provider=lambda: {})
        assert "should return a list of connections" in str(e.value)

        # Return is not connection type
        with pytest.raises(UnexpectedConnectionProviderReturn) as e:
            FlowInvoker(flow=EXAMPLE_FLOW, connection_provider=lambda: [1, 2])
        assert "should be connection type" in str(e.value)
