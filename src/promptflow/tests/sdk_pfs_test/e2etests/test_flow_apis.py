# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import os
from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = Path(__file__).parent.parent.parent
FLOW_PATH = "./tests/test_configs/flows/print_env_var"
IMAGE_PATH = "./tests/test_configs/datas/logo.jpg"
FLOW_WITH_IMAGE_PATH = "./tests/test_configs/flows/chat_flow_with_image"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestFlowAPIs:
    def test_get_flow_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow(flow_path=FLOW_PATH).data.decode("utf-8")
        assert flow_yaml_from_pfs == ('inputs:\n  key:\n    type: string\noutputs:\n  output:\n    type: string\n    '
                                      'reference: ${print_env.output.value}\nnodes:\n- name: print_env\n  '
                                      'type: python\n  source:\n    type: code\n    path: print_env.py\n  inputs:\n    '
                                      'key: ${inputs.key}\n')

    def test_get_eager_flow_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow(flow_path=str(EAGER_FLOW_ROOT / "builtin_llm")).json
        assert flow_yaml_from_pfs == {"entry": "builtin_call:flow_entry"}

    def test_flow_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.flows.test"):
            response = pfs_op.test_flow(
                flow_path=FLOW_PATH,
                request_body={"inputs": {"key": "value"}},
                status_code=200,
            ).json
        assert len(response) >= 1

    def test_get_flow_ux_inputs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            response = pfs_op.get_flow_ux_inputs(flow_path=Path(FLOW_PATH).absolute().as_posix()).json
        assert len(response) >= 0

    def test_image_save(self, pfs_op: PFSOperations) -> None:
        def image_to_base64(image_path):
            with Image.open(image_path) as img:
                with BytesIO() as buffer:
                    img.save(buffer, "JPEG")
                    return base64.b64encode(buffer.getvalue()).decode("utf-8")

        image_base64 = image_to_base64(IMAGE_PATH)
        extension = os.path.splitext(IMAGE_PATH)[1].lstrip(".")
        with check_activity_end_telemetry(expected_activities=[]):
            response = pfs_op.save_flow_image(
                flow_path=FLOW_PATH,
                request_body={
                    "base64_data": image_base64,
                    "extension": extension,
                },
            ).json

        os.remove(os.path.join(FLOW_PATH, response))

    def test_image_view(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            response = pfs_op.show_image(flow_path=FLOW_WITH_IMAGE_PATH, image_path="logo.jpg")
            assert response.status_code == 200
