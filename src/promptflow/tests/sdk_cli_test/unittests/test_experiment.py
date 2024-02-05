from pathlib import Path

import pytest
from ruamel.yaml import YAML

from promptflow._sdk._load_functions import _load_experiment_template
from promptflow._sdk._submitter.experiment_orchestrator import ExperimentTemplateTestContext
from promptflow._sdk.entities._experiment import Experiment, ExperimentData, ExperimentInput, FlowNode

TEST_ROOT = Path(__file__).parent.parent.parent
EXP_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"

yaml = YAML(typ="safe")


@pytest.mark.unittest
@pytest.mark.usefixtures("setup_experiment_table")
class TestExperiment:
    def test_experiment_from_template(self):
        template_path = EXP_ROOT / "basic-no-script-template"
        # Load template and create experiment
        template = _load_experiment_template(source=template_path)
        experiment = Experiment.from_template(template)
        # Assert experiment parts are resolved
        assert len(experiment.nodes) == 2
        assert all(isinstance(n, FlowNode) for n in experiment.nodes)
        assert len(experiment.data) == 1
        assert isinstance(experiment.data[0], ExperimentData)
        assert len(experiment.inputs) == 1
        assert isinstance(experiment.inputs[0], ExperimentInput)
        # Assert type is resolved
        assert experiment.inputs[0].default == 1
        # Pop schema and resolve path
        expected = dict(yaml.load(open(template_path / "basic.exp.yaml", "r", encoding="utf-8").read()))
        expected.pop("$schema")
        expected["data"][0]["path"] = (FLOW_ROOT / "web_classification" / "data.jsonl").absolute().as_posix()
        expected["nodes"][0]["path"] = (experiment._output_dir / "snapshots" / "main").absolute().as_posix()
        expected["nodes"][1]["path"] = (experiment._output_dir / "snapshots" / "eval").absolute().as_posix()
        experiment_dict = experiment._to_dict()
        assert experiment_dict["data"][0].items() == expected["data"][0].items()
        assert experiment_dict["nodes"][0].items() == expected["nodes"][0].items()
        assert experiment_dict["nodes"][1].items() == expected["nodes"][1].items()
        assert experiment_dict.items() >= expected.items()

    def test_flow_referenced_id_calculation(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = _load_experiment_template(source=template_path)
        test_context = ExperimentTemplateTestContext(template)
        assert test_context.node_name_to_referenced_id["main"] == []
        assert test_context.node_name_to_referenced_id["eval"] == [
            test_context.node_name_to_id["main"],
        ], "Eval node name should reference to main node id but not."
