import json
import os
import tempfile
from pathlib import Path

import pytest
from mock import mock
from ruamel.yaml import YAML

from promptflow import PFClient
from promptflow._core.operation_context import OperationContext
from promptflow._sdk._constants import PF_TRACE_CONTEXT, ExperimentStatus, RunStatus
from promptflow._sdk._errors import ExperimentValueError
from promptflow._sdk._load_functions import load_common
from promptflow._sdk.entities._experiment import CommandNode, Experiment, ExperimentTemplate, FlowNode

TEST_ROOT = Path(__file__).parent.parent.parent
EXP_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"


yaml = YAML(typ="safe")


@pytest.mark.e2etest
@pytest.mark.usefixtures("setup_experiment_table")
class TestExperiment:
    def test_experiment_from_template_with_script_node(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        # Assert command node load correctly
        assert len(experiment.nodes) == 4
        expected = dict(yaml.load(open(template_path, "r", encoding="utf-8").read()))
        experiment_dict = experiment._to_dict()
        assert isinstance(experiment.nodes[0], CommandNode)
        assert isinstance(experiment.nodes[1], FlowNode)
        assert isinstance(experiment.nodes[2], FlowNode)
        assert isinstance(experiment.nodes[3], CommandNode)
        gen_data_snapshot_path = experiment._output_dir / "snapshots" / "gen_data"
        echo_snapshot_path = experiment._output_dir / "snapshots" / "echo"
        expected["nodes"][0]["code"] = gen_data_snapshot_path.absolute().as_posix()
        expected["nodes"][3]["code"] = echo_snapshot_path.absolute().as_posix()
        expected["nodes"][3]["environment_variables"] = {}
        assert experiment_dict["nodes"][0].items() == expected["nodes"][0].items()
        assert experiment_dict["nodes"][3].items() == expected["nodes"][3].items()
        # Assert snapshots
        assert gen_data_snapshot_path.exists()
        file_count = len(list(gen_data_snapshot_path.rglob("*")))
        assert file_count == 1
        assert (gen_data_snapshot_path / "generate_data.py").exists()
        # Assert no file exists in echo path
        assert echo_snapshot_path.exists()
        file_count = len(list(echo_snapshot_path.rglob("*")))
        assert file_count == 0

    def test_experiment_create_and_get(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        assert len(client._experiments.list()) > 0
        exp_get = client._experiments.get(name=exp.name)
        assert exp_get._to_dict() == exp._to_dict()

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_start(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        exp = client._experiments.start(exp.name)
        assert PF_TRACE_CONTEXT in os.environ
        attributes = json.loads(os.environ[PF_TRACE_CONTEXT]).get("attributes")
        assert attributes.get("experiment") == exp.name
        assert attributes.get("referenced.run_id", "").startswith("main")
        assert exp.status == ExperimentStatus.TERMINATED
        # Assert main run
        assert len(exp.node_runs["main"]) > 0
        main_run = client.runs.get(name=exp.node_runs["main"][0]["name"])
        assert main_run.status == RunStatus.COMPLETED
        assert main_run.variant == "${summarize_text_content.variant_0}"
        assert main_run.display_name == "main"
        assert len(exp.node_runs["eval"]) > 0
        # Assert eval run and metrics
        eval_run = client.runs.get(name=exp.node_runs["eval"][0]["name"])
        assert eval_run.status == RunStatus.COMPLETED
        assert eval_run.display_name == "eval"
        metrics = client.runs.get_metrics(name=eval_run.name)
        assert "accuracy" in metrics

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_experiment_with_script_start(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        template = load_common(ExperimentTemplate, source=template_path)
        experiment = Experiment.from_template(template)
        client = PFClient()
        exp = client._experiments.create_or_update(experiment)
        exp = client._experiments.start(exp.name)
        assert exp.status == ExperimentStatus.TERMINATED
        assert len(exp.node_runs) == 4
        for key, val in exp.node_runs.items():
            assert val[0]["status"] == RunStatus.COMPLETED, f"Node {key} run failed"

    @pytest.mark.usefixtures("use_secrets_config_file", "recording_injection", "setup_local_connection")
    def test_flow_test_with_experiment(self):
        def _assert_result(result):
            assert "main" in result, "Node main not in result"
            assert "category" in result["main"], "Node main.category not in result"
            assert "evidence" in result["main"], "Node main.evidence not in result"
            assert "eval" in result, "Node eval not in result"
            assert "grade" in result["eval"], "Node eval.grade not in result"

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True

            template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
            target_flow_path = FLOW_ROOT / "web_classification" / "flow.dag.yaml"
            client = PFClient()
            # Test with inputs
            result = client.flows.test(
                target_flow_path,
                experiment=template_path,
                inputs={"url": "https://www.youtube.com/watch?v=kYqRtjDBci8", "answer": "Channel"},
            )
            _assert_result(result)
            # Assert line run id is set by executor when running test
            assert PF_TRACE_CONTEXT in os.environ
            attributes = json.loads(os.environ[PF_TRACE_CONTEXT]).get("attributes")
            assert attributes.get("experiment") == template_path.resolve().absolute().as_posix()
            assert attributes.get("referenced.line_run_id", "").startswith("main")
            assert OperationContext.get_instance()._get_otel_attributes().get("line_run_id") is not None
            expected_output_path = (
                Path(tempfile.gettempdir()) / ".promptflow/sessions/default" / "basic-no-script-template"
            )
            assert expected_output_path.resolve().exists()
            # Assert eval metric exists
            assert (expected_output_path / "eval" / "flow.metrics.json").exists()
            # Test with default data and custom path
            expected_output_path = Path(tempfile.gettempdir()) / ".promptflow/my_custom"
            result = client.flows.test(target_flow_path, experiment=template_path, output_path=expected_output_path)
            _assert_result(result)
            assert expected_output_path.resolve().exists()
            # Assert eval metric exists
            assert (expected_output_path / "eval" / "flow.metrics.json").exists()

    def test_flow_not_in_experiment(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        target_flow_path = FLOW_ROOT / "chat_flow" / "flow.dag.yaml"
        client = PFClient()
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            with pytest.raises(ExperimentValueError) as error:
                client.flows.test(
                    target_flow_path,
                    experiment=template_path,
                )
            assert "not found in experiment" in str(error.value)
