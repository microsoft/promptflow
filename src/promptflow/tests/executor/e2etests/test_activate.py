import pytest

from promptflow.contracts.run_info import Status
from promptflow.executor.flow_executor import FlowExecutor, LineResult

from ..utils import get_flow_inputs, get_yaml_file


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorActivate:
    def test_activate(self, dev_connections):
        flow_folder = "conditional_flow_with_activate"
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections)
        results = executor.exec_line(get_flow_inputs(flow_folder))
        self.assert_activate_flow_result(results)

    def assert_activate_flow_result(self, result: LineResult):
        # Validate the flow status
        assert result.run_info.status == Status.Completed

        # Validate the flow output
        assert isinstance(result.output, dict)
        expected_output = {
            "investigation_method": {
                "first": "Skip job info extractor",
                "second": "Execute incident info extractor",
            }
        }
        assert expected_output.items() <= result.output.items()

        # Validate the flow node run infos for the completed nodes
        assert len(result.node_run_infos) == 9
        completed_nodes = ["incident_id_extractor", "incident_info_extractor", "investigation_steps",
                           "retriever_summary", "tsg_retriever", "kql_tsg_retriever", "investigation_method"]
        completed_nodes_run_infos = [result.node_run_infos[i] for i in completed_nodes]
        assert all([node.status == Status.Completed for node in completed_nodes_run_infos])

        # Validate the flow node run infos for the skipped nodes
        skipped_nodes = ["job_info_extractor", "icm_retriever"]
        skipped_nodes_run_infos = [result.node_run_infos[i] for i in skipped_nodes]
        assert all([node.status == Status.Skipped for node in skipped_nodes_run_infos])
        assert all([node.output is None for node in skipped_nodes_run_infos])
