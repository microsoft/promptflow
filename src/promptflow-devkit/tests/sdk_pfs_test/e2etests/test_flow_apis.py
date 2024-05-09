# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


import sys
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOW_PATH = "./tests/test_configs/flows/print_env_var"
IMAGE_PATH = "./tests/test_configs/datas/logo.jpg"
FLOW_WITH_IMAGE_PATH = "./tests/test_configs/flows/chat_flow_with_image"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"
PROMPTY_ROOT = TEST_ROOT / "test_configs/prompty"


def clear_module_cache(module_name):
    try:
        del sys.modules[module_name]
    except Exception:
        pass


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

    def test_flow_infer_signature(self, pfs_op: PFSOperations) -> None:
        # prompty
        response = pfs_op.test_flow_infer_signature(
            flow_path=(Path(PROMPTY_ROOT) / "prompty_example.prompty").absolute().as_posix(),
            include_primitive_output=True,
            status_code=200,
        ).json
        assert response == {
            "init": {
                "api": {"default": "chat", "type": "string"},
                "configuration": {"type": "object"},
                "parameters": {"type": "object"},
                "response": {"default": "first", "type": "string"},
            },
            "inputs": {
                "firstName": {"default": "John", "type": "string"},
                "lastName": {"default": "Doh", "type": "string"},
                "question": {"type": "string"},
            },
            "outputs": {"output": {"type": "string"}},
        }

        # flex flow
        response = pfs_op.test_flow_infer_signature(
            flow_path=(Path(EAGER_FLOW_ROOT) / "builtin_llm").absolute().as_posix(),
            include_primitive_output=True,
            status_code=200,
        ).json
        assert response == {
            "inputs": {
                "chat_history": {"default": "[]", "type": "list"},
                "question": {"default": "What is ChatGPT?", "type": "string"},
                "stream": {"default": "False", "type": "bool"},
            },
            "outputs": {"output": {"type": "string"}},
        }

    def test_eager_flow_test_with_yaml(self, pfs_op: PFSOperations) -> None:
        clear_module_cache("entry")
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
            ).json
        assert len(response) >= 1

    def test_eager_flow_with_user_code_error(self, pfs_op: PFSOperations) -> None:
        clear_module_cache("entry")
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test", "completion_status": "Failure"},
            ]
        ):
            response = pfs_op.test_flow(
                flow_path=Path(f"{EAGER_FLOW_ROOT}/exception_in_user_code/").absolute().as_posix(),
                request_body={},
                status_code=404,
            )
        assert "Traceback (most recent call last):" in response.text

    def test_prompty_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.flows.test"},
            ]
        ):
            response = pfs_op.test_flow(
                flow_path=Path(f"{PROMPTY_ROOT}/prompty_with_chat_history.prompty").absolute().as_posix(),
                request_body={"inputs": {"question": "what is the result of 3+3?"}},
                status_code=200,
            ).json
        assert len(response) >= 1
