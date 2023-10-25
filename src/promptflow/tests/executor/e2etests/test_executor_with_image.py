import os
import shutil
from pathlib import Path

import pytest

from promptflow._utils.multimedia_utils import _create_image_from_file, is_multimedia_dict
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import Status
from promptflow.executor import BatchEngine, FlowExecutor
from promptflow.executor.flow_executor import BulkResult, LineResult
from promptflow.storage._run_storage import DefaultRunStorage

from ..utils import FLOW_ROOT, get_flow_folder, get_yaml_file, is_image_file, is_jsonl_file

SIMPLE_IMAGE_FLOW = "python_tool_with_simple_image"
COMPOSITE_IMAGE_FLOW = "python_tool_with_composite_image"
CHAT_FLOW_WITH_IMAGE = "chat_flow_with_image"
SIMPLE_IMAGE_FLOW_PATH = FLOW_ROOT / SIMPLE_IMAGE_FLOW
COMPOSITE_IMAGE_FLOW_PATH = FLOW_ROOT / COMPOSITE_IMAGE_FLOW
CHAT_FLOW_WITH_IMAGE_PATH = FLOW_ROOT / CHAT_FLOW_WITH_IMAGE
IMAGE_URL = (
    "https://github.com/microsoft/promptflow/blob/93776a0631abf991896ab07d294f62082d5df3f3/src"
    "/promptflow/tests/test_configs/datas/test_image.jpg?raw=true"
)


def get_test_cases_for_simple_input():
    image = _create_image_from_file(SIMPLE_IMAGE_FLOW_PATH / "logo.jpg")
    inputs = [
        {"data:image/jpg;path": str(SIMPLE_IMAGE_FLOW_PATH / "logo.jpg")},
        {"data:image/jpg;base64": image.to_base64()},
        {"data:image/jpg;url": IMAGE_URL},
        str(SIMPLE_IMAGE_FLOW_PATH / "logo.jpg"),
        image.to_base64(),
        IMAGE_URL,
    ]
    return [(SIMPLE_IMAGE_FLOW, {"image": input}) for input in inputs]


def get_test_cases_for_composite_input():
    image_1 = _create_image_from_file(COMPOSITE_IMAGE_FLOW_PATH / "logo.jpg")
    image_2 = _create_image_from_file(COMPOSITE_IMAGE_FLOW_PATH / "logo_2.png")
    inputs = [
        [
            {"data:image/jpg;path": str(COMPOSITE_IMAGE_FLOW_PATH / "logo.jpg")},
            {"data:image/png;path": str(COMPOSITE_IMAGE_FLOW_PATH / "logo_2.png")},
        ],
        [{"data:image/jpg;base64": image_1.to_base64()}, {"data:image/png;base64": image_2.to_base64()}],
        [{"data:image/jpg;url": IMAGE_URL}, {"data:image/png;url": IMAGE_URL}],
    ]
    return [
        (COMPOSITE_IMAGE_FLOW, {"image_list": input, "image_dict": {"image_1": input[0], "image_2": input[1]}})
        for input in inputs
    ]


def get_test_cases_for_node_run():
    image = {"data:image/jpg;path": str(SIMPLE_IMAGE_FLOW_PATH / "logo.jpg")}
    simple_image_input = {"image": image}
    image_list = [{"data:image/jpg;path": "logo.jpg"}, {"data:image/png;path": "logo_2.png"}]
    image_dict = {
        "image_dict": {
            "image_1": {"data:image/jpg;path": "logo.jpg"},
            "image_2": {"data:image/png;path": "logo_2.png"},
        }
    }
    composite_image_input = {"image_list": image_list, "image_dcit": image_dict}

    return [
        (SIMPLE_IMAGE_FLOW, "python_node", simple_image_input, None),
        (SIMPLE_IMAGE_FLOW, "python_node_2", simple_image_input, {"python_node": image}),
        (COMPOSITE_IMAGE_FLOW, "python_node", composite_image_input, None),
        (COMPOSITE_IMAGE_FLOW, "python_node_2", composite_image_input, None),
        (
            COMPOSITE_IMAGE_FLOW,
            "python_node_3",
            composite_image_input,
            {"python_node": image_list, "python_node_2": image_dict},
        ),
    ]


def assert_contain_image_reference(value):
    assert not isinstance(value, Image)
    if isinstance(value, list):
        for item in value:
            assert_contain_image_reference(item)
    elif isinstance(value, dict):
        if is_multimedia_dict(value):
            path = list(value.values())[0]
            assert isinstance(path, str)
            assert path.endswith(".jpg") or path.endswith(".jpeg") or path.endswith(".png")
        else:
            for _, v in value.items():
                assert_contain_image_reference(v)


def assert_contain_image_object(value):
    if isinstance(value, list):
        for item in value:
            assert_contain_image_object(item)
    elif isinstance(value, dict):
        assert not is_multimedia_dict(value)
        for _, v in value.items():
            assert_contain_image_object(v)
    else:
        assert isinstance(value, Image)


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorWithImage:
    @pytest.mark.parametrize(
        "flow_folder, inputs", get_test_cases_for_simple_input() + get_test_cases_for_composite_input()
    )
    def test_executor_exec_line_with_image(self, flow_folder, inputs, dev_connections):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, storage=storage)
        flow_result = executor.exec_line(inputs)
        assert isinstance(flow_result.output, dict)
        assert_contain_image_object(flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert_contain_image_reference(flow_result.run_info)
        for _, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert_contain_image_reference(node_run_info)

    def test_executor_exec_line_with_chat_flow(self, dev_connections):
        flow_folder = CHAT_FLOW_WITH_IMAGE
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, storage=storage)
        flow_result = executor.exec_line({})
        assert isinstance(flow_result.output, dict)
        assert_contain_image_object(flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert_contain_image_reference(flow_result.run_info)
        for _, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert_contain_image_reference(node_run_info)

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs", get_test_cases_for_node_run()
    )
    def test_executor_exec_node_with_image(
        self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections
    ):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            output_sub_dir=("./temp"),
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert_contain_image_reference(run_info)

    def test_executor_batch_engine_with_image(self):
        executor = FlowExecutor.create(get_yaml_file(SIMPLE_IMAGE_FLOW), {})
        input_dirs = {"data": "image_inputs/inputs.jsonl"}
        inputs_mapping = {"image": "${data.image}"}
        output_dir = Path("outputs")
        bulk_result = BatchEngine(executor).run(input_dirs, inputs_mapping, output_dir)

        assert isinstance(bulk_result, BulkResult)
        for i, output in enumerate(bulk_result.outputs):
            assert isinstance(output, dict)
            assert "line_number" in output, f"line_number is not in {i}th output {output}"
            assert output["line_number"] == i, f"line_number is not correct in {i}th output {output}"
            assert "data:image/png;path" in output["output"], f"image is not in {i}th output {output}"
        for i, line_result in enumerate(bulk_result.line_results):
            assert isinstance(line_result, LineResult)
            assert line_result.run_info.status == Status.Completed, f"{i}th line got {line_result.run_info.status}"

        output_dir = get_flow_folder(SIMPLE_IMAGE_FLOW) / output_dir
        assert all(is_jsonl_file(output_file) or is_image_file(output_file) for output_file in output_dir.iterdir())
        shutil.rmtree(output_dir)
