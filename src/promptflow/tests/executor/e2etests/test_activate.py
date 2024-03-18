from pathlib import Path
from tempfile import mkdtemp
from typing import Dict

import pytest

from promptflow._constants import OUTPUT_FILE_NAME
from promptflow._utils.logger_utils import LogContext
from promptflow.batch._batch_engine import BatchEngine
from promptflow.batch._result import BatchResult
from promptflow.contracts._errors import FlowDefinitionError
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor

from ..utils import (
    WRONG_FLOW_ROOT,
    MemoryRunStorage,
    get_flow_expected_result,
    get_flow_expected_status_summary,
    get_flow_folder,
    get_flow_inputs,
    get_flow_inputs_file,
    get_yaml_file,
    load_jsonl,
)

ACTIVATE_FLOW_TEST_CASES = [
    "conditional_flow_with_activate",
    "activate_with_no_inputs",
    "all_depedencies_bypassed_with_activate_met",
    "activate_condition_always_met",
]


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestExecutorActivate:
    @pytest.mark.parametrize("flow_folder", ACTIVATE_FLOW_TEST_CASES)
    def test_flow_run_activate(self, dev_connections, flow_folder):
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        results = executor.exec_line(get_flow_inputs(flow_folder))
        # Assert the flow result
        expected_result = get_flow_expected_result(flow_folder)
        expected_result = expected_result[0] if isinstance(expected_result, list) else get_flow_expected_result
        self.assert_activate_flow_run_result(results.run_info, expected_result)
        self.assert_activate_node_run_result(results.node_run_infos, expected_result)

    def test_batch_run_activate(self, dev_connections):
        flow_folder = "conditional_flow_with_activate"
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder),
            get_flow_folder(flow_folder),
            connections=dev_connections,
            storage=mem_run_storage,
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="inputs.json")}
        inputs_mapping = {"incident_id": "${data.incident_id}", "incident_content": "${data.incident_content}"}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        expected_result = get_flow_expected_result(flow_folder)
        expected_status_summary = get_flow_expected_status_summary(flow_folder)
        self.assert_activate_bulk_run_result(
            output_dir, mem_run_storage, batch_results, expected_result, expected_status_summary
        )

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

    def test_invalid_activate_config(self):
        flow_folder = "invalid_activate_config"
        with pytest.raises(FlowDefinitionError) as ex:
            FlowExecutor.create(get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT), {})
        assert ex.value.message == (
            "The definition of activate config for node divide_num is incorrect. "
            "Please check your flow yaml and resubmit."
        )

    def test_aggregate_bypassed_nodes(self):
        flow_folder = "conditional_flow_with_aggregate_bypassed"
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections={}, storage=mem_run_storage
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder, file_name="inputs.json")}
        inputs_mapping = {"case": "${data.case}", "value": "${data.value}"}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        expected_result = get_flow_expected_result(flow_folder)
        expected_status_summary = get_flow_expected_status_summary(flow_folder)
        self.assert_activate_bulk_run_result(
            output_dir, mem_run_storage, batch_results, expected_result, expected_status_summary
        )

        # Validate the aggregate result
        for node_run_info in mem_run_storage._node_runs.values():
            if node_run_info.node == "aggregation_double":
                assert node_run_info.status == Status.Completed
                assert node_run_info.output == 3
            elif node_run_info.node == "aggregation_square":
                assert node_run_info.status == Status.Completed
                assert node_run_info.output == 12.5

    def assert_activate_bulk_run_result(
        self,
        output_dir: Path,
        mem_run_storage: MemoryRunStorage,
        batch_result: BatchResult,
        expected_result,
        expected_status_summary,
    ):
        # Validate the flow outputs
        outputs = load_jsonl(output_dir / OUTPUT_FILE_NAME)
        for i, output in enumerate(outputs):
            expected_outputs = expected_result[i]["expected_outputs"].copy()
            expected_outputs.update({"line_number": i})
            assert output == expected_outputs

        # Validate the flow line results
        flow_runs = {k: v for k, v in sorted(mem_run_storage._flow_runs.items(), key=lambda item: item[1].index)}
        for i, (flow_run_id, flow_run_info) in enumerate(flow_runs.items()):
            self.assert_activate_flow_run_result(flow_run_info, expected_result[i])
            node_run_infos = {
                node_run_info.node: node_run_info
                for node_run_info in mem_run_storage._node_runs.values()
                if node_run_info.parent_run_id == flow_run_id
            }
            self.assert_activate_node_run_result(node_run_infos, expected_result[i])

        # Validate the flow status summary
        assert batch_result.total_lines == batch_result.completed_lines
        assert batch_result.node_status == expected_status_summary

    def assert_activate_flow_run_result(self, flow_run_info: FlowRunInfo, expected_result):
        # Validate the flow status
        assert flow_run_info.status == Status.Completed

        # Validate the flow output
        assert isinstance(flow_run_info.output, dict)
        assert flow_run_info.output == expected_result["expected_outputs"]

    def assert_activate_node_run_result(self, node_run_infos: Dict[str, NodeRunInfo], expected_result):
        # Validate the flow node run infos for the completed nodes
        assert len(node_run_infos) == expected_result["expected_node_count"]
        expected_bypassed_nodes = expected_result["expected_bypassed_nodes"]
        completed_nodes_run_infos = [
            run_info for i, run_info in node_run_infos.items() if i not in expected_bypassed_nodes
        ]
        assert all([node.status == Status.Completed for node in completed_nodes_run_infos])

        # Validate the flow node run infos for the bypassed nodes
        bypassed_nodes_run_infos = [node_run_infos[i] for i in expected_bypassed_nodes]
        assert all([node.status == Status.Bypassed for node in bypassed_nodes_run_infos])
        assert all([node.output is None for node in bypassed_nodes_run_infos])
