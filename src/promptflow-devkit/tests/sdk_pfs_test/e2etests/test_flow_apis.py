# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOW_PATH = "./tests/test_configs/flows/print_env_var"
IMAGE_PATH = "./tests/test_configs/datas/logo.jpg"
FLOW_WITH_IMAGE_PATH = "./tests/test_configs/flows/chat_flow_with_image"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestFlowAPIs:
    def test_flow_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.flows.test"):
            response = pfs_op.test_flow(
                flow_path=FLOW_PATH,
                request_body={"inputs": {"key": "value"}},
                status_code=200,
            ).json
        assert len(response) >= 1

    def test_eager_flow_test_with_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.flows.test"):
            response = pfs_op.test_flow(
                flow_path=Path(f"{EAGER_FLOW_ROOT}/simple_with_yaml/").absolute().as_posix(),
                request_body={"inputs": {"input_val": "val1"}},
                status_code=200,
            ).json
        assert len(response) >= 1

    def test_eager_flow_test_with_init(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.flows.test"):
            response = pfs_op.test_flow(
                flow_path=Path(f"{EAGER_FLOW_ROOT}/basic_callable_class/").absolute().as_posix(),
                request_body={"inputs": {"func_input": "input"}, "init": {"obj_input": "val"}},
                status_code=200,
            ).json
        assert len(response) >= 1
