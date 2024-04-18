# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import os
from io import BytesIO
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from PIL import Image

from ..utils import PFSOperations, check_activity_end_telemetry

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
FLOW_PATH = "./tests/test_configs/flows/print_env_var"
IMAGE_PATH = "./tests/test_configs/datas/logo.jpg"
FLOW_WITH_IMAGE_PATH = "./tests/test_configs/flows/chat_flow_with_image"
EAGER_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"
EXPERIMENT_ROOT = TEST_ROOT / "test_configs/experiments"


@pytest.mark.e2etest
class TestUIAPIs:
    def test_get_flow_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow_yaml(flow_path=FLOW_PATH).data.decode("utf-8")
        assert flow_yaml_from_pfs == (
            "inputs:\n  key:\n    type: string\noutputs:\n  output:\n    type: string\n    "
            "reference: ${print_env.output.value}\nnodes:\n- name: print_env\n  "
            "type: python\n  source:\n    type: code\n    path: print_env.py\n  inputs:\n    "
            "key: ${inputs.key}\n"
        )

    def test_get_eager_flow_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            flow_yaml_from_pfs = pfs_op.get_flow_yaml(flow_path=str(EAGER_FLOW_ROOT / "builtin_llm")).data.decode(
                "utf-8"
            )
        assert flow_yaml_from_pfs == "entry: builtin_call:flow_entry\n"

    def test_get_experiment_yaml(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(expected_activities=[]):
            experiment_yaml_from_pfs = pfs_op.get_experiment_yaml(
                flow_path=FLOW_PATH,
                experiment_path=(EXPERIMENT_ROOT / "basic-no-script-template/basic.exp.yaml").as_posix(),
            ).data.decode("utf-8")
        assert experiment_yaml_from_pfs == (
            "$schema: https://azuremlschemas.azureedge.net/promptflow/latest/"
            "Experiment.schema.json\n\ndescription: Basic experiment without script "
            "node\n\ndata:\n- name: my_data\n  path: ../../flows/web_classification/"
            "data.jsonl\n\ninputs:\n- name: my_input\n  type: int\n  default: 1\n\n"
            "nodes:\n- name: main\n  type: flow\n  path: ../../flows/"
            "web_classification/flow.dag.yaml\n  inputs:\n    "
            "url: ${data.my_data.url}\n  variant: ${summarize_text_content.variant_0}"
            "\n  environment_variables: {}\n  connections: {}\n\n- name: "
            "eval\n  type: flow\n  path: ../../flows/eval-classification-accuracy\n  "
            "inputs:\n    groundtruth: ${data.my_data.answer}    "
            '# No node can be named with "data"\n    '
            "prediction: ${main.outputs.category}\n  environment_variables: {}\n  "
            "connections: {}\n"
        )

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
