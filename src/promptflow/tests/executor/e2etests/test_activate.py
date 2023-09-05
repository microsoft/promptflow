import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor._errors import OutputReferenceBypassed
from promptflow.executor.flow_executor import BulkResult, FlowExecutor, LineResult

from ..utils import (
    WRONG_FLOW_ROOT,
    get_bulk_inputs,
    get_flow_expected_result,
    get_flow_expected_status_summary,
    get_flow_inputs,
    get_yaml_file,
)

ACTIVATE_FLOW_TEST_CASES = ["conditional_flow_with_activate", "activate_with_no_inputs"]


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorActivate:
    @pytest.mark.parametrize("flow_folder", ACTIVATE_FLOW_TEST_CASES)
    def test_flow_run_activate(self, dev_connections, flow_folder):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        results = executor.exec_line(get_flow_inputs(flow_folder))
        # Assert the flow result
        expected_result = get_flow_expected_result(flow_folder)
        self.assert_activate_flow_run_result(results, expected_result[0])

    def test_bulk_run_activate(self, dev_connections):
        flow_folder = "conditional_flow_with_activate"
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        results = executor.exec_bulk(get_bulk_inputs(flow_folder))
        expected_result = get_flow_expected_result(flow_folder)
        expected_status_summary = get_flow_expected_status_summary(flow_folder)
        self.assert_activate_bulk_run_result(results, expected_result, expected_status_summary)

    def test_wrong_flow_activate(self, dev_connections):
        flow_folder = "all_nodes_bypassed"
        executor = FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)
        with pytest.raises(OutputReferenceBypassed) as e:
            executor.exec_line(get_flow_inputs(flow_folder, WRONG_FLOW_ROOT))
        error_message = "Failed to extract output because the reference node 'third_node' has been bypassed."
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))

    def assert_activate_bulk_run_result(self, result: BulkResult, expected_result, expected_status_summary):
        # Validate the flow outputs
        for i, output in enumerate(result.outputs):
            expected_outputs = expected_result[i]["expected_outputs"].copy()
            expected_outputs.update({"line_number": i})
            assert output == expected_outputs

        # Validate the flow line results
        for i, line_result in enumerate(result.line_results):
            self.assert_activate_flow_run_result(line_result, expected_result[i])

        # Validate the flow status summary
        status_summary = result.get_status_summary()
        assert status_summary == expected_status_summary

    def assert_activate_flow_run_result(self, result: LineResult, expected_result):
        # Validate the flow status
        assert result.run_info.status == Status.Completed

        # Validate the flow output
        assert isinstance(result.output, dict)
        assert result.output == expected_result["expected_outputs"]

        # Validate the flow node run infos for the completed nodes
        assert len(result.node_run_infos) == expected_result["expected_node_count"]
        expected_bypassed_nodes = expected_result["expected_bypassed_nodes"]
        completed_nodes_run_infos = [
            run_info for i, run_info in result.node_run_infos.items() if i not in expected_bypassed_nodes
        ]
        assert all([node.status == Status.Completed for node in completed_nodes_run_infos])

        # Validate the flow node run infos for the bypassed nodes
        bypassed_nodes_run_infos = [result.node_run_infos[i] for i in expected_bypassed_nodes]
        assert all([node.status == Status.Bypassed for node in bypassed_nodes_run_infos])
        assert all([node.output is None for node in bypassed_nodes_run_infos])
