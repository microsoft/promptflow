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
            "first": "Skip job info extractor",
        }
        assert expected_output.items() <= result.output["investigation_method"].items()

        # Validate the flow node run infos
        assert len(result.node_run_infos) == 8

        node_run_info = result.node_run_infos["incident_id_extractor"]
        assert node_run_info.status == Status.Completed
        assert node_run_info.output == {
            "has_incident_id": True,
            "incident_id": 0,
            "incident_content": "Incident 418856448 : Stale App Deployment for App promptflow"
        }

        node_run_info = result.node_run_infos["incident_info_extractor"]
        assert node_run_info.status == Status.Completed
        assert node_run_info.output == {
            "retriever": "icm",
            "incident_content": "Incident 418856448 : Stale App Deployment for App promptflow"
        }

        node_run_info = result.node_run_infos["icm_retriever"]
        assert node_run_info.status == Status.Completed
        assert node_run_info.output == "ICM: Incident 418856448 : Stale App Deployment for App promptflow"

        node_run_info = result.node_run_infos["investigation_steps"]
        assert node_run_info.status == Status.Completed

        node_run_info = result.node_run_infos["investigation_method"]
        assert node_run_info.status == Status.Completed
        assert expected_output.items() <= node_run_info.output.items()

        # Validate the flow node run infos for the skipped nodes
        node_run_info = result.node_run_infos["job_info_extractor"]
        assert node_run_info.status == Status.Skipped
        assert node_run_info.output is None

        node_run_info = result.node_run_infos["tsg_retriever"]
        assert node_run_info.status == Status.Skipped
        assert node_run_info.output is None

        node_run_info = result.node_run_infos["kql_retriever"]
        assert node_run_info.status == Status.Skipped
        assert node_run_info.output is None
