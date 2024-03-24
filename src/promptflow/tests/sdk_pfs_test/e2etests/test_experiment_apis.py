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
                experiment_path=EXPERIMENT_PATH.absolute().as_posix()).data.decode("utf-8")
        assert experiment_yaml_from_pfs == ('$schema: https://azuremlschemas.azureedge.net/promptflow/latest/'
                                            'Experiment.schema.json\n\ndescription: Basic experiment without script '
                                            'node\n\ndata:\n- name: my_data\n  path: ../../flows/web_classification/'
                                            'data.jsonl\n\ninputs:\n- name: my_input\n  type: int\n  default: 1\n\n'
                                            'nodes:\n- name: main\n  type: flow\n  path: ../../flows/web_classification'
                                            '/flow.dag.yaml\n  inputs:\n    url: ${data.my_data.url}\n  '
                                            'variant: ${summarize_text_content.variant_0}\n  environment_variables: {}'
                                            '\n  connections: {}\n\n- name: eval\n  type: flow\n  '
                                            'path: ../../flows/eval-classification-accuracy\n  inputs:\n    '
                                            'groundtruth: ${data.my_data.answer}    '
                                            '# No node can be named with "data"\n    '
                                            'prediction: ${main.outputs.category}\n  environment_variables: {}\n  '
                                            'connections: {}\n')
