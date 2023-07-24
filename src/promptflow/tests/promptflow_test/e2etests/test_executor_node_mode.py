import sys
from pathlib import Path

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow_test.utils import _save_result_in_temp_folder, load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests/node_mode_requests"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
@pytest.mark.flaky(reruns=3, reruns_delay=1)
class TestNodeMode:
    @pytest.mark.parametrize(
        "file_name, run_mode, expected_node_num",
        [
            ("example_flow_node_mode.json", RunMode.SingleNode, 1),
            ("example_flow_node_mode.json", RunMode.FromNode, 3),
            ("eval_flow_node_mode.json", RunMode.SingleNode, 1),
            ("eval_flow_node_mode.json", RunMode.FromNode, 2),
            ("my_flow_single_node.json", RunMode.SingleNode, 1),
        ],
    )
    def test_run_mode(self, basic_executor, file_name, run_mode, expected_node_num) -> None:
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=run_mode)

        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        _save_result_in_temp_folder(result, file_name)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert result["flow_runs"] is None
        assert len(result["node_runs"]) == expected_node_num
        for run in result["node_runs"]:
            assert isinstance(run, dict)
            assert run["status"] == "Completed"

    def test_single_node_variant(self, basic_executor):
        file_name = "variants_flow_single_node.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )

        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        _save_result_in_temp_folder(result, file_name)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert result["flow_runs"] is None

        assert len(result["node_runs"]) == 1
        for run in result["node_runs"]:
            assert isinstance(run, dict)
            assert run["status"] == "Completed"
            assert run["variant_id"] == "variant1"

    def test_single_node_complete_for_incorrect_flow_info(self, basic_executor):
        """
        The single node submission request payload might miss information about other nodes.
        Single node should still complete in this case.
        """
        file_name = "example_flow_incorrect_other_nodes.json"
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(
            source=json_file, source_run_id=json_file.stem, run_mode=RunMode.SingleNode
        )

        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        _save_result_in_temp_folder(result, file_name)
        assert isinstance(result, dict)
        assert "flow_runs" in result
        assert result["flow_runs"] is None
        assert len(result["node_runs"]) == 1
        for run in result["node_runs"]:
            assert isinstance(run, dict)
            assert run["status"] == "Completed"

    @pytest.mark.parametrize(
        "file_name, run_mode, connection_names",
        [
            ("example_flow_node_mode.json", RunMode.SingleNode, ["azure_open_ai_connection"]),
            ("example_flow_node_mode.json", RunMode.FromNode, ["azure_open_ai_connection"]),
            ("eval_flow_node_mode.json", RunMode.SingleNode, []),
            ("eval_flow_node_mode.json", RunMode.FromNode, []),
            ("my_flow_single_node.json", RunMode.SingleNode, ["azure_open_ai_connection"]),
            ("test_connection_flow.json", RunMode.SingleNode, ["bing_config"]),
            (
                "test_connection_flow.json",
                RunMode.FromNode,
                ["bing_config", "bing_config2", "azure_open_ai_connection"],
            ),
        ],
    )
    def test_single_node_connection_resolve(self, file_name, run_mode, connection_names):
        json_file = Path(JSON_DATA_ROOT) / file_name
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=run_mode)
        assert request_data.submission_data.get_node_connection_names(run_mode) == set(connection_names)
