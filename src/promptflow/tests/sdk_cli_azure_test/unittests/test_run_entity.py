# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from unittest.mock import Mock

import pytest

from promptflow._sdk.entities import Run
from promptflow.exceptions import UserErrorException

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.unittest
class TestRun:
    def test_input_mapping_types(self, pf):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input")
        # run with dict inputs
        run = Run(
            flow=flow_path,
            data=data_path,
            column_mapping=dict(key={"a": 1}),
        )
        rest_run = run._to_rest_object()
        assert rest_run.inputs_mapping == {"key": '{"a": 1}'}

        # run with list inputs
        run = Run(
            flow=flow_path,
            data=data_path,
            column_mapping=dict(key=["a", "b"]),
        )
        rest_run = run._to_rest_object()
        assert rest_run.inputs_mapping == {"key": '["a", "b"]'}

        # unsupported inputs
        run = Run(
            flow=flow_path,
            data=data_path,
            column_mapping=dict(key=Mock()),
        )
        with pytest.raises(UserErrorException):
            run._to_rest_object()

        run = Run(flow=flow_path, data=data_path, column_mapping="str")
        with pytest.raises(UserErrorException):
            run._to_rest_object()
