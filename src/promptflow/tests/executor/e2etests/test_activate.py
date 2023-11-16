from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._utils.logger_utils import LogContext
from promptflow.batch import BatchEngine
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._result import BatchResult, LineResult

from ..utils import (
    get_flow_expected_result,
    get_flow_expected_status_summary,
    get_flow_folder,
    get_flow_inputs,
    get_flow_inputs_file,
    get_yaml_file,
)

ACTIVATE_FLOW_TEST_CASES = [
    "conditional_flow_with_activate",
    "activate_with_no_inputs",
    "all_depedencies_bypassed_with_activate_met",
    "activate_condition_always_met",
]


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorActivate:
    @pytest.mark.parametrize("flow_folder", ACTIVATE_FLOW_TEST_CASES)
    def test_flow_run_activate(self, dev_connections, flow_folder):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        results = executor.exec_line(get_flow_inputs(flow_folder))
        # Assert the flow result
        expected_result = get_flow_expected_result(flow_folder)
        expected_result = expected_result[0] if isinstance(expected_result, list) else get_flow_expected_result
        self.assert_activate_flow_run_result(results, expected_result)

    def test_batch_run_activate(self, dev_connections):
        flow_folder = "conditional_flow_with_activate"
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="inputs.json")}
        inputs_mapping = {"incident_id": "${data.incident_id}", "incident_content": "${data.incident_content}"}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        expected_result = get_flow_expected_result(flow_folder)
        expected_status_summary = get_flow_expected_status_summary(flow_folder)
        self.assert_activate_bulk_run_result(batch_results, expected_result, expected_status_summary)

    def test_all_nodes_bypassed(self, dev_connections):
        flow_folder = "all_nodes_bypassed"
        file_path = Path(mkdtemp()) / "flow.log"
        with LogContext(file_path):
            executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
            result = executor.exec_line(get_flow_inputs(flow_folder))
        assert result.output["result"] is None
        with open(file_path) as fin:
            content = fin.read()
            assert "The node referenced by output:'third_node' is bypassed, which is not recommended." in content

    def test_aggregate_bypassed_nodes(self):
        flow_folder = "conditional_flow_with_aggregate_bypassed"
        batch_engine = BatchEngine(get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections={})
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="inputs.json")}
        inputs_mapping = {"case": "${data.case}", "value": "${data.value}"}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        expected_result = get_flow_expected_result(flow_folder)
        expected_status_summary = get_flow_expected_status_summary(flow_folder)
        self.assert_activate_bulk_run_result(batch_results, expected_result, expected_status_summary)

        # Validate the aggregate result
        assert batch_results.aggr_results.node_run_infos["aggregation_double"].output == 3
        assert batch_results.aggr_results.node_run_infos["aggregation_square"].output == 12.5

    def assert_activate_bulk_run_result(self, result: BatchResult, expected_result, expected_status_summary):
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
