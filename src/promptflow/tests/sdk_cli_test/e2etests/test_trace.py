from pathlib import Path
from unittest.mock import patch

import pytest
from mock import mock

from promptflow._sdk._pf_client import PFClient

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()


@pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
@pytest.mark.e2etest
@pytest.mark.sdk_test
class TestTraceWithDevKit:
    def test_flow_test_trace_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
                pf.test(flow=Path(f"{FLOWS_DIR}/web_classification").absolute(), inputs=inputs)
                assert mock_start_trace.call_count == 1

    def test_flow_test_single_node_trace_not_enabled(self, pf: PFClient) -> None:
        import promptflow.tracing._start_trace

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with patch.object(promptflow.tracing._start_trace, "start_trace") as mock_start_trace:
                pf.test(
                    flow=Path(f"{FLOWS_DIR}/web_classification").absolute(),
                    inputs={"fetch_url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g"},
                    node="fetch_text_content_from_url",
                )
                assert mock_start_trace.call_count == 0
