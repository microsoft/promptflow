# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest
from marshmallow import ValidationError

from promptflow._sdk.entities._flows import FlexFlow, Flow
from promptflow.client import load_flow
from promptflow.exceptions import UserErrorException, ValidationException

FLOWS_DIR = Path("./tests/test_configs/flows")
EAGER_FLOWS_DIR = Path("./tests/test_configs/eager_flows")


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestRun:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"source": EAGER_FLOWS_DIR / "simple_with_yaml"},
            {"source": EAGER_FLOWS_DIR / "simple_with_yaml" / "flow.flex.yaml"},
        ],
    )
    def test_eager_flow_load(self, kwargs):
        flow = load_flow(**kwargs)
        assert isinstance(flow, FlexFlow)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"source": FLOWS_DIR / "print_input_flow"},
            {"source": FLOWS_DIR / "print_input_flow" / "flow.dag.yaml"},
        ],
    )
    def test_dag_flow_load(self, kwargs):
        flow = load_flow(**kwargs)
        assert isinstance(flow, Flow)

    def test_flow_load_advanced(self):
        flow = load_flow(source=EAGER_FLOWS_DIR / "flow_with_environment")
        assert isinstance(flow, FlexFlow)
        assert flow._data["environment"] == {"python_requirements_txt": "requirements.txt"}

    @pytest.mark.parametrize(
        "kwargs, error_message, exception_type",
        [
            (
                {"source": EAGER_FLOWS_DIR / "invalid_extra_fields_nodes"},
                "{'nodes': ['Unknown field.']}",
                ValidationError,
            ),
            (
                {
                    "source": EAGER_FLOWS_DIR / "invalid_illegal_path",
                },
                "{'path': ['Unknown field.']}",
                ValidationError,
            ),
        ],
    )
    def test_flow_load_invalid(self, kwargs, error_message, exception_type):
        with pytest.raises(exception_type) as e:
            load_flow(**kwargs)

        assert error_message in str(e.value)

    def test_multiple_flow_load(self):
        with pytest.raises(ValidationException) as e:
            load_flow(EAGER_FLOWS_DIR / "multiple_flow_yaml")

        assert "Multiple files flow.dag.yaml, flow.flex.yaml exist in " in str(e.value)

    def test_multiple_flex_load(self):
        with pytest.raises(ValidationException) as e:
            load_flow(EAGER_FLOWS_DIR / "multiple_flex_yaml")

        assert "Multiple files flow.flex.yaml, flow.flex.yml exist in " in str(e.value)

    def test_specify_flow_load(self):
        load_flow(EAGER_FLOWS_DIR / "multiple_flow_yaml" / "flow.dag.yaml")
        load_flow(EAGER_FLOWS_DIR / "multiple_flow_yaml" / "flow.flex.yaml")

    def test_flow_path_not_exist(self):
        flow_path = EAGER_FLOWS_DIR / "flow_path_not_exist"
        with pytest.raises(UserErrorException) as e:
            load_flow(flow_path)

        assert f"Flow path {flow_path.absolute().as_posix()} does not exist." in str(e.value)

    def test_flow_file_not_exist(self):
        flow_path = EAGER_FLOWS_DIR / "multiple_flow_yaml" / "flow.dag2.yaml"
        with pytest.raises(UserErrorException) as e:
            load_flow(flow_path)

        assert f"Flow file {flow_path.absolute().as_posix()} does not exist." in str(e.value)

    def test_flow_file_not_exist2(self):
        flow_path = EAGER_FLOWS_DIR / "simple_without_yaml"
        with pytest.raises(UserErrorException) as e:
            load_flow(flow_path)

        assert f"Have found neither flow.dag.yaml nor flow.flex.yaml in {flow_path.absolute().as_posix()}" in str(
            e.value
        )

    @pytest.mark.parametrize(
        "flow_file",
        [
            "flow.flex.yaml",
            "flow_with_sample_ref.yaml",
            "flow_with_sample_inner_ref.yaml",
        ],
    )
    def test_flex_flow_sample_ref(self, flow_file):
        expected_sample_dict = {
            "init": {"obj_input1": "val1", "obj_input2": "val2"},
            "inputs": {"func_input1": "val1", "func_input2": "val2"},
        }
        flow_path = EAGER_FLOWS_DIR / "flow_with_sample" / flow_file
        flow = load_flow(flow_path)
        assert flow.sample == expected_sample_dict

    @pytest.mark.parametrize(
        "flow_file",
        [
            "flow.flex.yaml",
            "flow_with_sample_ref.yaml",
            "flow_with_sample_inner_ref.yaml",
        ],
    )
    def test_function_flex_flow_sample_ref(self, flow_file):
        expected_sample_dict = {
            "inputs": {"func_input1": "val1", "func_input2": "val2"},
        }
        flow_path = EAGER_FLOWS_DIR / "function_flow_with_sample" / flow_file
        flow = load_flow(flow_path)
        assert flow.sample == expected_sample_dict
