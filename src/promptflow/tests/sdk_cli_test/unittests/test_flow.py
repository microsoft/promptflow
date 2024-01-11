# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest
from marshmallow import ValidationError

from promptflow import load_flow
from promptflow._sdk.entities._eager_flow import EagerFlow
from promptflow._sdk.entities._flow import ProtectedFlow
from promptflow.exceptions import UserErrorException

FLOWS_DIR = Path("./tests/test_configs/flows")
EAGER_FLOWS_DIR = Path("./tests/test_configs/eager_flows")


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestRun:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"source": EAGER_FLOWS_DIR / "simple_with_yaml"},
            {"source": EAGER_FLOWS_DIR / "simple_with_yaml" / "flow.dag.yaml"},
            {"source": EAGER_FLOWS_DIR / "simple_without_yaml" / "entry.py", "entry": "my_flow"},
            {"source": EAGER_FLOWS_DIR / "multiple_entries" / "entry1.py", "entry": "my_flow1"},
            {"source": EAGER_FLOWS_DIR / "multiple_entries" / "entry1.py", "entry": "my_flow2"},
        ],
    )
    def test_eager_flow_load(self, kwargs):
        flow = load_flow(**kwargs)
        assert isinstance(flow, EagerFlow)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"source": FLOWS_DIR / "print_input_flow"},
            {"source": FLOWS_DIR / "print_input_flow" / "flow.dag.yaml"},
        ],
    )
    def test_dag_flow_load(self, kwargs):
        flow = load_flow(**kwargs)
        assert isinstance(flow, ProtectedFlow)

    def test_flow_load_advanced(self):
        flow = load_flow(source=EAGER_FLOWS_DIR / "flow_with_environment")
        assert isinstance(flow, EagerFlow)
        assert flow._data["environment"] == {"python_requirements_txt": "requirements.txt"}

    @pytest.mark.parametrize(
        "kwargs, error_message, exception_type",
        [
            (
                {
                    "source": EAGER_FLOWS_DIR / "multiple_entries" / "entry1.py",
                },
                "Entry function is not specified",
                UserErrorException,
            ),
            (
                {
                    "source": EAGER_FLOWS_DIR / "multiple_entries" / "not_exist.py",
                },
                "does not exist",
                UserErrorException,
            ),
            (
                {
                    "source": EAGER_FLOWS_DIR / "invalid_no_path",
                },
                "{'path': ['Missing data for required field.']}",
                ValidationError,
            ),
            (
                {
                    "source": EAGER_FLOWS_DIR / "invalid_illegal_path",
                },
                "Can't find directory or file in resolved absolute path:",
                ValidationError,
            ),
            (
                {"source": EAGER_FLOWS_DIR / "invalid_extra_fields_nodes"},
                "{'nodes': ['Unknown field.']}",
                ValidationError,
            ),
        ],
    )
    def test_flow_load_invalid(self, kwargs, error_message, exception_type):
        with pytest.raises(exception_type) as e:
            load_flow(**kwargs)

        assert error_message in str(e.value)
