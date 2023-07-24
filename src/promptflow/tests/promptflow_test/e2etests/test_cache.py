import sys
import uuid
from pathlib import Path
from typing import List

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow_test.utils import load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"
NODE_MODE_FOLDER = "node_mode_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


def _set_enable_cache(request_data: SubmitFlowRequest, nodes_to_cache: List[str]) -> SubmitFlowRequest:
    """Mark node's enabled cache as true."""
    submission_data = request_data.submission_data
    nodes = submission_data.flow.nodes
    for n in nodes:
        if n.name in nodes_to_cache:
            n.enable_cache = True
    return request_data


def _assert_run_2_cache_run_1(run_2: dict, run_1: dict):
    assert run_2["cached_run_id"] == run_1["run_id"]
    assert run_2["cached_flow_run_id"] == run_1["flow_run_id"]
    assert run_2["result"] == run_1["result"]
    assert run_2["end_time"] is not None
    assert run_2["start_time"] is not None


@pytest.mark.usefixtures("use_secrets_config_file", "local_executor")
@pytest.mark.e2etest
class TestCache:
    @pytest.mark.parametrize(
        "file_name, cached_nodes",
        [
            ("example_flow.json", ["Bing_search_1", "teenager_vote", "middle_aged_man_vote"]),
        ],
    )
    def test_flow(self, local_executor, file_name, cached_nodes) -> None:
        """Test the basic flow that has three flow runs."""
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)

        # Mark node's enabled cache as true.
        request_data = _set_enable_cache(request_data, cached_nodes)

        # Submit flow first time.
        result_1 = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        # Submit flow again with a different flow run id, all nodes should be reused.
        request_data.flow_run_id = str(uuid.uuid4())
        result_2 = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)

        for run in result_1["flow_runs"]:
            assert isinstance(run, dict)
            assert run["status"] == "Completed", f"Flow run {run['run_id']} failed."

        for run in result_2["flow_runs"]:
            assert isinstance(run, dict)
            assert run["status"] == "Completed", f"Flow run {run['run_id']} failed."

        assert len(result_1["node_runs"]) == len(result_2["node_runs"])

        for (run_1, run_2) in zip(result_1["node_runs"], result_2["node_runs"]):
            if run_1["node"] in cached_nodes:
                _assert_run_2_cache_run_1(run_2, run_1)

    def test_single_node(self, local_executor):
        file_name = "example_flow_node_mode.json"
        json_file = Path(JSON_DATA_ROOT) / NODE_MODE_FOLDER / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )
        cached_nodes = [request_data.submission_data.node_name]
        request_data = _set_enable_cache(request_data, cached_nodes)

        result_1 = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        local_executor._run_tracker._flow_runs.clear()
        local_executor._run_tracker._node_runs.clear()
        result_2 = local_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        assert len(result_1["node_runs"]) == len(result_2["node_runs"]) == 1
        run_1 = result_1.get("node_runs")[0]
        run_2 = result_2.get("node_runs")[0]
        _assert_run_2_cache_run_1(run_2, run_1)
