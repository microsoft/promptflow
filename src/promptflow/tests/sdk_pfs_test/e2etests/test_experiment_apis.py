# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = Path(__file__).parent.parent.parent
EXPERIMENT_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"


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
                body={"experiment_template": (EXPERIMENT_ROOT / "basic-no-script-template/basic.exp.yaml").as_posix()}
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://www.youtube.com/watch?v=kYqRtjDBci8"
        }
        assert "eval" in experiment

    def test_experiment_test_with_override_input(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.get", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "basic-no-script-template/basic_without_binding.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (FLOW_ROOT / "web_classification" / "flow.dag.yaml").as_posix(),
                    "inputs": {"url": "https://arxiv.org/abs/2307.04767", "answer": "Academic", "evidence": "Both"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://arxiv.org/abs/2307.04767",
            "answer": "Academic",
            "evidence": "Both",
        }
        assert "eval" in experiment

        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.get", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (EXPERIMENT_ROOT / "basic-no-script-template/basic.exp.yaml").as_posix(),
                    "override_flow_path": (FLOW_ROOT / "web_classification" / "flow.dag.yaml").as_posix(),
                    "inputs": {"url": "https://arxiv.org/abs/2307.04767", "answer": "Academic", "evidence": "Both"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://arxiv.org/abs/2307.04767",
            "answer": "Academic",
            "evidence": "Both",
        }
        assert "eval" in experiment

        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.get", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (EXPERIMENT_ROOT / "basic-no-script-template/basic1.exp.yaml").as_posix(),
                    "override_flow_path": (FLOW_ROOT / "web_classification" / "flow.dag.yaml").as_posix(),
                    "inputs": {"url": "https://arxiv.org/abs/2307.04767", "answer": "Academic", "evidence": "Both"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://arxiv.org/abs/2307.04767",
            "answer": "Academic",
            "evidence": "Both",
        }
        assert "eval" in experiment

    def test_experiment_test_with_binding_flow_input(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.connections.get", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={"experiment_template": (EXPERIMENT_ROOT / "basic-no-script-template/basic1.exp.yaml").as_posix()}
            ).json
        assert "main" in experiment
        assert "eval" in experiment

    def test_experiment_test_with_skip_node(self, pfs_op: PFSOperations):
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment.test"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (EXPERIMENT_ROOT / "basic-no-script-template/basic.exp.yaml").as_posix(),
                    "skip_flow": (FLOW_ROOT / "web_classification" / "flow.dag.yaml").as_posix(),
                    "skip_flow_output": {"category": "Channel", "evidence": "Both"},
                    "skip_flow_run_id": "123",
                }
            ).json
        assert "eval" in experiment
