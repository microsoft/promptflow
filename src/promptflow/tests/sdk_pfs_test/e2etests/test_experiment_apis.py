# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from ..utils import PFSOperations, check_activity_end_telemetry

FLOW_PATH = "./tests/test_configs/flows/print_env_var"
EXPERIMENT_PATH = (
    Path(__file__).parent.parent.parent / "test_configs/experiments/basic-no-script-template/basic.exp.yaml"
)


@pytest.mark.e2etest
class TestExperimentAPIs:
    def test_experiment_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.get", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={"template": EXPERIMENT_PATH.absolute().as_posix()}
            ).json
        assert "main" in experiment
        assert "eval" in experiment

    def test_get_experiment_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            experiment_yaml_from_pfs = pfs_op.get_experiment(
                flow_path=FLOW_PATH,
                experiment_path=EXPERIMENT_PATH.absolute().as_posix()).json
        assert experiment_yaml_from_pfs == {
            '$schema': 'https://azuremlschemas.azureedge.net/promptflow/latest/Experiment.schema.json',
            'description': 'Basic experiment without script node',
            'data': [{'name': 'my_data', 'path': '../../flows/web_classification/data.jsonl'}],
            'inputs': [{'name': 'my_input', 'type': 'int', 'default': 1}],
            'nodes': [
                {
                    'name': 'main',
                    'type': 'flow',
                    'path': '../../flows/web_classification/flow.dag.yaml',
                    'inputs': {'url': '${data.my_data.url}'},
                    'variant': '${summarize_text_content.variant_0}',
                    'environment_variables': {},
                    'connections': {}
                },
                {
                    'name': 'eval',
                    'type': 'flow',
                    'path': '../../flows/eval-classification-accuracy',
                    'inputs': {'groundtruth': '${data.my_data.answer}', 'prediction': '${main.outputs.category}'},
                    'environment_variables': {},
                    'connections': {}}]
        }
