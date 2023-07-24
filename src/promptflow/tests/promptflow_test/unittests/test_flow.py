from pathlib import Path

import pytest

from promptflow_test.utils import load_and_convert_to_raw

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"


@pytest.mark.unittest
class TestFlow:
    @pytest.mark.parametrize(
        "test_units",
        [
            ("serpapi_e2e.json", {"serp_connection"}),
            (
                "batch_request_e2e.json",
                {
                    "azure_open_ai_connection",
                    "bing_config",
                },
            ),
            ("qa_with_bing.json", {"azure_open_ai_connection", "bing_config"}),
            ("eval_flow.json", set()),
            (
                "consume_connection.json",
                {"azure_open_ai_connection", "bing_config", "custom_connection"},
            ),
            ("custom_connection_flow.json", {"custom_connection"}),
            ("custom_python_with_connection.json", {"azure_open_ai_connection"}),
        ],
    )
    def test_flow_get_connection_names(self, test_units) -> None:
        """Test the basic flow that has three flow runs."""
        file_name, expected_connection_names = test_units
        json_file = Path(JSON_DATA_ROOT) / file_name
        request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        flow = request.submission_data.flow
        assert flow.get_connection_names() == expected_connection_names

    def test_is_referenced_by_other_node(self) -> None:
        """Test node is referenced by other node."""
        json_file = Path(JSON_DATA_ROOT) / "qa_with_bing.json"
        request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        flow = request.submission_data.flow

        for node in flow.nodes:
            if node.name == "infer_intent":
                assert flow.is_referenced_by_other_node(node)
            elif node.name == "Bing_search_1":
                assert flow.is_referenced_by_other_node(node)
            elif node.name == "combine_search_result_1":
                assert flow.is_referenced_by_other_node(node)
            elif node.name == "qa_with_sources":
                assert not flow.is_referenced_by_other_node(node)
