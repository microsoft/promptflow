# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from _constants import PROMPTFLOW_ROOT

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
EXPERIMENT_ROOT = TEST_ROOT / "test_configs/experiments"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"
EAGER_FLOWS_DIR = TEST_ROOT / "test_configs/eager_flows"


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestExperimentAPIs:
    def test_experiment_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/basic.exp.yaml"
                    ).as_posix()
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://www.youtube.com/watch?v=kYqRtjDBci8"
        }
        assert "eval" in experiment

    def test_experiment_with_run_id(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/basic.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (FLOW_ROOT / "dummy_web_classification" / "flow.dag.yaml").as_posix(),
                    "main_flow_run_id": "123",
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://www.youtube.com/watch?v=kYqRtjDBci8"
        }
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["root_run_id"] == "123"
        assert "eval" in experiment

    def test_experiment_eager_flow_with_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={"experiment_template": (EXPERIMENT_ROOT / "eager-flow-exp-template/flow.exp.yaml").as_posix()}
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "models": ["model"],
            "text": "text",
        }
        assert "main2" in experiment
        assert "main3" in experiment

    def test_experiment_eager_flow_with_init(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "class-based-eager-flow-exp-template/flow.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (EAGER_FLOWS_DIR / "basic_callable_class" / "flow.flex.yaml").as_posix(),
                    "main_flow_init": {"obj_input": "val3"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "func_input": "val1",
        }
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["output"]["obj_input"] == "val3"
        assert "main2" in experiment

    def test_experiment_test_with_override_input(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/basic_without_binding/basic.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (FLOW_ROOT / "dummy_web_classification" / "flow.dag.yaml").as_posix(),
                    "inputs": {"url": "https://arxiv.org/abs/2307.04767", "answer": "Academic", "evidence": "Both"},
                    "main_flow_run_id": "123",
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://arxiv.org/abs/2307.04767",
            "answer": "Academic",
            "evidence": "Both",
        }
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["root_run_id"] == "123"
        assert "eval" in experiment

        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/basic.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (FLOW_ROOT / "dummy_web_classification" / "flow.dag.yaml").as_posix(),
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
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/bind_to_flow_input/basic.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (FLOW_ROOT / "dummy_web_classification" / "flow.dag.yaml").as_posix(),
                    "inputs": {"url": "https://arxiv.org/abs/2307.04767", "answer": "Academic", "evidence": "Both"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "url": "https://arxiv.org/abs/2307.04767",
            "answer": "Academic",
            "evidence": "Both",
        }
        assert "eval" in experiment

    def test_experiment_eager_flow_with_override_input(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "eager-flow-exp-template/basic_without_binding/flow.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (
                        EAGER_FLOWS_DIR / "flow_with_dataclass_output" / "flow.flex.yaml"
                    ).as_posix(),
                    "inputs": {"models": ["model1"], "text": "text1"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "models": ["model1"],
            "text": "text1",
        }
        assert "main2" in experiment
        assert "main3" in experiment

        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (EXPERIMENT_ROOT / "eager-flow-exp-template/flow.exp.yaml").as_posix(),
                    "override_flow_path": (
                        EAGER_FLOWS_DIR / "flow_with_dataclass_output" / "flow.flex.yaml"
                    ).as_posix(),
                    "inputs": {"models": ["model1"], "text": "text1"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "models": ["model1"],
            "text": "text1",
        }
        assert "main2" in experiment
        assert "main3" in experiment

        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "eager-flow-exp-template/bind_to_flow_input/flow.exp.yaml"
                    ).as_posix(),
                    "override_flow_path": (
                        EAGER_FLOWS_DIR / "flow_with_dataclass_output" / "flow.flex.yaml"
                    ).as_posix(),
                    "inputs": {"models": ["model1"], "text": "text1"},
                }
            ).json
        assert "main" in experiment and experiment["main"]["detail"]["flow_runs"][0]["inputs"] == {
            "models": ["model1"],
            "text": "text1",
        }
        assert "main2" in experiment
        assert "main3" in experiment

    def test_experiment_test_with_binding_flow_input(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/bind_to_flow_input/basic.exp.yaml"
                    ).as_posix()
                }
            ).json
        assert "main" in experiment
        assert "eval" in experiment

    def test_experiment_test_with_skip_node(self, pfs_op: PFSOperations):
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test_with_skip(
                body={
                    "experiment_template": (
                        EXPERIMENT_ROOT / "dummy-basic-no-script-template/basic.exp.yaml"
                    ).as_posix(),
                    "skip_flow": (FLOW_ROOT / "dummy_web_classification" / "flow.dag.yaml").as_posix(),
                    "skip_flow_output": {"category": "Channel", "evidence": "Both"},
                    "skip_flow_run_id": "123",
                }
            ).json
        assert "eval" in experiment
        assert len(experiment) == 1

    def test_experiment_eager_flow_with_skip_node(self, pfs_op: PFSOperations):
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.flows.test", "first_call": False},
                {"activity_name": "pf.experiment._test_flow", "activity_type": "InternalCall"},
            ]
        ):
            experiment = pfs_op.experiment_test_with_skip(
                body={
                    "experiment_template": (EXPERIMENT_ROOT / "eager-flow-exp-template/flow.exp.yaml").as_posix(),
                    "skip_flow": (EAGER_FLOWS_DIR / "flow_with_dataclass_output" / "flow.flex.yaml").as_posix(),
                    "skip_flow_output": {"models": ["model"], "text": "text"},
                    "skip_flow_run_id": "123",
                }
            ).json
        assert "main2" in experiment
        assert "main3" in experiment
        assert len(experiment) == 2
