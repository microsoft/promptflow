from unittest.mock import PropertyMock, patch

import pytest

from promptflow._version import VERSION
from promptflow.contracts.run_mode import RunMode
from promptflow.core.operation_context import OperationContext


def set_run_mode(context: OperationContext, run_mode: RunMode):
    """This method simulates the runtime.execute_request()

    It is aimed to set the run_mode into operation context.
    """
    context.run_mode = run_mode.name if run_mode is not None else ""


@pytest.mark.unittest
class TestOperationContext:
    def test_get_user_agent(self):
        operation_context = OperationContext()
        assert operation_context.get_user_agent() == f"promptflow-sdk/{VERSION}"

        operation_context.user_agent = "test_agent/0.0.2"
        assert operation_context.get_user_agent() == f"promptflow-sdk/{VERSION} test_agent/0.0.2"

    @pytest.mark.parametrize(
        "run_mode, expected",
        [
            (RunMode.Flow, "Flow"),
            (RunMode.SingleNode, "SingleNode"),
            (RunMode.FromNode, "FromNode"),
            (RunMode.BulkTest, "BulkTest"),
            (RunMode.Eval, "Eval"),
        ],
    )
    def test_run_mode(self, run_mode, expected):
        context = OperationContext()
        set_run_mode(context, run_mode)
        assert context.run_mode == expected

    def test_get_http_headers(self):
        context = OperationContext()
        headers = context.get_http_headers()
        assert len(headers) > 0

        for key in headers.keys():
            assert key.startswith("ms-azure-ai-promptflow-") or key == "x-ms-useragent"
            assert "_" not in key

        assert headers["x-ms-useragent"] is not None
        assert headers["ms-azure-ai-promptflow-called-from"] == "others"

    def test_mock_info_headers(self):
        with patch.object(OperationContext, "promptflow_info", new_callable=PropertyMock) as mock_promptflow_info:
            mock_promptflow_info.return_value = {
                "workspace-name": "",
                "subscription-id": None,
                "flow-id": 123,
            }

            context = OperationContext()
            headers = context.get_http_headers()

            assert headers["ms-azure-ai-promptflow-workspace-name"] == ""
            assert headers["ms-azure-ai-promptflow-subscription-id"] == ""
            assert headers["ms-azure-ai-promptflow-flow-id"] == "123"

            mock_promptflow_info.assert_called_once()
