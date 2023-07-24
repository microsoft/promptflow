import sys
from pathlib import Path

import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutionCoodinator
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info
from promptflow_test.utils import load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_wrong_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
class TestExecutorErrorFromTool:
    @pytest.mark.parametrize(
        "file_name, message",
        [
            (
                "bing_invalid_api_key.json",
                "Flow run failed due to the error: Access denied due to invalid subscription key or wrong API endpoint."
                " Make sure to provide a valid key for an active subscription and use a correct regional API endpoint"
                " for your resource. code: 401. For more info, please refer to "
                "https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/reference/error-codes",
            ),
        ],
    )
    def test_bing_tool_error(self, basic_executor: FlowExecutionCoodinator, file_name, message):
        json_file = JSON_DATA_ROOT / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        # Inject the wrong confi into connections
        basic_executor._connections_in_env["bing_wrong_config"] = {
            "type": "BingConnection",
            "value": {"api_key": "hello"},
            "module": "promptflow.connections",
        }
        result = basic_executor.exec_request_raw(raw_request=request_data)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert isinstance(result["flow_runs"], list)
        assert 2 == len(result["flow_runs"]), f"Expected 2 flow run but got {len(result['flow_runs'])}"
        # There 1 node run because the flow failed before the second node run
        assert 1 == len(result["node_runs"]), f"Expected 1 node run but got {len(result['node_runs'])}"
        root_run = deserialize_flow_run_info(result["flow_runs"][0])
        assert Status.Failed == root_run.status, f"Expected status {Status.Failed} but got {root_run.status}"
        message_in_run = root_run.error["message"]
        assert message_in_run == message, f"Expected message {message} but got {message_in_run}"
