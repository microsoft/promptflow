# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ..utils import PFSOperations, check_activity_end_telemetry

FLOW_PATH = "./tests/test_configs/flows/print_env_var"
IMAGE_PATH = "./tests/test_configs/datas/logo.jpg"


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestFlowAPIs:
    def test_get_flow_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow(flow_path=FLOW_PATH).json
        assert flow_yaml_from_pfs == {
            "inputs": {"key": {"type": "string"}},
            "outputs": {"output": {"type": "string", "reference": "${print_env.output.value}"}},
            "nodes": [
                {
                    "name": "print_env",
                    "type": "python",
                    "source": {"type": "code", "path": "print_env.py"},
                    "inputs": {"key": "${inputs.key}"},
                }
            ],
        }

    def test_flow_test(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.flows.test"):
            response = pfs_op.test_flow(
                request_body={"flow": Path(FLOW_PATH).absolute().as_posix(), "inputs": {"key": "value"}},
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
                request_body={
                    "base64_data": image_base64,
                    "extension": extension,
                },
            ).json
        os.remove(response)

    def test_image_view(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            response = pfs_op.get_image_url(image_path=Path(IMAGE_PATH).absolute().as_posix()).json
            match = re.match(".*/image/(.+)/(.+)", response)
            assert match
            directory, filename = match.groups()
            response = pfs_op.view_image(directory, filename)
            assert response.data
