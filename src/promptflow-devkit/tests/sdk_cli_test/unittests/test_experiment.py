from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from ruamel.yaml import YAML

from promptflow._sdk._errors import MultipleExperimentTemplateError, NoExperimentTemplateError
from promptflow._sdk._load_functions import _load_experiment_template
from promptflow._sdk._orchestrator.experiment_orchestrator import ExperimentTemplateTestContext
from promptflow._sdk.entities._experiment import CommandNode, Experiment, ExperimentData, ExperimentInput, FlowNode

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
EXP_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"

yaml = YAML(typ="safe")


@pytest.mark.unittest
@pytest.mark.usefixtures("setup_experiment_table")
class TestExperiment:
    def test_experiment_template_not_exists(self):
        template_path = EXP_ROOT
        with pytest.raises(NoExperimentTemplateError):
            _load_experiment_template(source=template_path)
        with pytest.raises(NoExperimentTemplateError):
            _load_experiment_template(source=template_path / "not-exist.exp.yaml")
        template_path = EXP_ROOT / "basic-script-template"
        with pytest.raises(MultipleExperimentTemplateError):
            _load_experiment_template(source=template_path)

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
        experiment_dict["nodes"][0].pop("init")
        assert experiment_dict["nodes"][0].items() == expected["nodes"][0].items()
        experiment_dict["nodes"][1].pop("init")
        assert experiment_dict["nodes"][1].items() == expected["nodes"][1].items()
        assert experiment_dict.items() >= expected.items()

    def test_script_node_experiment_template(self):
        template_path = EXP_ROOT / "basic-script-template" / "basic-script.exp.yaml"
        # Load template and create experiment
        # Test override output path resolve correctly
        template = _load_experiment_template(source=template_path)
        experiment = Experiment.from_template(template)
        # Assert command node output resolved
        assert isinstance(experiment.nodes[0], CommandNode)
        assert isinstance(experiment.nodes[3], CommandNode)
        assert experiment.nodes[3].outputs["output_path"] == Path(template_path).parent.as_posix()

    def test_flow_referenced_id_calculation(self):
        template_path = EXP_ROOT / "basic-no-script-template" / "basic.exp.yaml"
        # Load template and create experiment
        template = _load_experiment_template(source=template_path)
        test_context = ExperimentTemplateTestContext(template)
        assert test_context.node_name_to_referenced_id["main"] == []
        assert test_context.node_name_to_referenced_id["eval"] == [
            test_context.node_name_to_id["main"],
        ], "Eval node name should reference to main node id but not."
