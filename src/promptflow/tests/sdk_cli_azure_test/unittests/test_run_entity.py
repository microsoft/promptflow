# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

from promptflow._sdk.entities import Run
from promptflow._utils.flow_utils import get_flow_lineage_id
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

    def test_flow_id(self):
        # same flow id for same flow in same GIT repo
        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input")

        # run with dict inputs
        session_id1 = get_flow_lineage_id(flow_path)
        session_id2 = get_flow_lineage_id(flow_path)

        assert session_id1 == session_id2

        # same flow id for same flow in same device
        with TemporaryDirectory() as tmp_dir:
            shutil.copytree(f"{FLOWS_DIR}/flow_with_dict_input", f"{tmp_dir}/flow_with_dict_input")

            session_id3 = get_flow_lineage_id(f"{tmp_dir}/flow_with_dict_input")

            session_id4 = get_flow_lineage_id(f"{tmp_dir}/flow_with_dict_input")

            assert session_id3 == session_id4
            assert session_id3 != session_id1
