import os
from pathlib import Path

import pytest

from promptflow._utils.multimedia_utils import BasicMultimediaProcessor, ImageProcessor, OpenaiVisionMultimediaProcessor
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.executor.flow_executor import FlowExecutor
from promptflow.storage._run_storage import DefaultRunStorage

from ...utils import get_flow_folder, get_yaml_file

SIMPLE_IMAGE_FLOW = "python_tool_with_simple_image"
SAMPLE_IMAGE_FLOW_WITH_DEFAULT = "python_tool_with_simple_image_with_default"
SIMPLE_IMAGE_WITH_INVALID_DEFAULT_VALUE_FLOW = "python_tool_with_invalid_default_value"
COMPOSITE_IMAGE_FLOW = "python_tool_with_composite_image"
CHAT_FLOW_WITH_IMAGE = "chat_flow_with_image"
EVAL_FLOW_WITH_SIMPLE_IMAGE = "eval_flow_with_simple_image"
EVAL_FLOW_WITH_COMPOSITE_IMAGE = "eval_flow_with_composite_image"
NESTED_API_CALLS_FLOW = "python_tool_with_image_nested_api_calls"

SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE = "python_tool_with_openai_vision_image"
CHAT_FLOW_WITH_OPENAI_VISION_IMAGE = "chat_flow_with_openai_vision_image"

IMAGE_URL = (
    "https://raw.githubusercontent.com/microsoft/promptflow/main/src/promptflow/tests/test_configs/datas/logo.jpg"
)


def get_test_cases_for_simple_input(flow_folder):
    working_dir = get_flow_folder(flow_folder)
    image = ImageProcessor.create_image_from_file(working_dir / "logo.jpg")
    inputs = [
        {"data:image/jpg;path": str(working_dir / "logo.jpg")},
        {"data:image/jpg;base64": image.to_base64()},
        {"data:image/jpg;url": IMAGE_URL},
        str(working_dir / "logo.jpg"),
        image.to_base64(),
        IMAGE_URL,
    ]
    return [(flow_folder, {"image": input}) for input in inputs]


def get_test_cases_for_composite_input(flow_folder):
    working_dir = get_flow_folder(flow_folder)
    image_1 = ImageProcessor.create_image_from_file(working_dir / "logo.jpg")
    image_2 = ImageProcessor.create_image_from_file(working_dir / "logo_2.png")
    inputs = [
        [
            {"data:image/jpg;path": str(working_dir / "logo.jpg")},
            {"data:image/png;path": str(working_dir / "logo_2.png")},
        ],
        [{"data:image/jpg;base64": image_1.to_base64()}, {"data:image/png;base64": image_2.to_base64()}],
        [{"data:image/jpg;url": IMAGE_URL}, {"data:image/png;url": IMAGE_URL}],
    ]
    return [
        (flow_folder, {"image_list": input, "image_dict": {"image_1": input[0], "image_2": input[1]}})
        for input in inputs
    ]


def get_test_cases_for_node_run():
    image = {"data:image/jpg;path": str(get_flow_folder(SIMPLE_IMAGE_FLOW) / "logo.jpg")}
    simple_image_input = {"image": image}
    image_list = [{"data:image/jpg;path": "logo.jpg"}, {"data:image/png;path": "logo_2.png"}]
    image_dict = {
        "image_dict": {
            "image_1": {"data:image/jpg;path": "logo.jpg"},
            "image_2": {"data:image/png;path": "logo_2.png"},
        }
    }
    composite_image_input = {"image_list": image_list, "image_dict": image_dict}

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


def contain_image_reference(value, parent_path="temp", multimedia_processor=BasicMultimediaProcessor()):
    if isinstance(value, (FlowRunInfo, RunInfo)):
        assert contain_image_reference(value.api_calls, parent_path, multimedia_processor=multimedia_processor)
        assert contain_image_reference(value.inputs, parent_path, multimedia_processor=multimedia_processor)
        assert contain_image_reference(value.output, parent_path, multimedia_processor=multimedia_processor)
        return True
    assert not isinstance(value, Image)
    if isinstance(value, list):
        return any(
            contain_image_reference(item, parent_path, multimedia_processor=multimedia_processor) for item in value
        )
    if isinstance(value, dict):
        if multimedia_processor.is_multimedia_dict(value):
            if isinstance(multimedia_processor, BasicMultimediaProcessor):
                v = list(value.values())[0]
            else:
                v = value[value["type"]].get("url", "") or value[value["type"]].get("path", "")
            assert isinstance(v, str)
            assert ImageProcessor.is_url(v) or str(Path(v).parent) == parent_path
            return True
        return any(
            contain_image_reference(v, parent_path, multimedia_processor=multimedia_processor) for v in value.values()
        )
    return False


def contain_image_object(value, multimedia_processor=BasicMultimediaProcessor()):
    if isinstance(value, list):
        return any(contain_image_object(item) for item in value)
    elif isinstance(value, dict):
        assert not multimedia_processor.is_multimedia_dict(value)
        return any(contain_image_object(v) for v in value.values())
    else:
        return isinstance(value, Image)


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorWithImage:
    @pytest.mark.parametrize(
        "flow_folder, inputs",
        get_test_cases_for_simple_input(SIMPLE_IMAGE_FLOW)
        + get_test_cases_for_composite_input(COMPOSITE_IMAGE_FLOW)
        + [(CHAT_FLOW_WITH_IMAGE, {}), (NESTED_API_CALLS_FLOW, {})],
    )
    def test_executor_exec_line_with_image(self, flow_folder, inputs, dev_connections):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, storage=storage)
        flow_result = executor.exec_line(inputs)
        assert isinstance(flow_result.output, dict)
        assert contain_image_object(flow_result.output)
        # Assert output also contains plain text.
        assert any(isinstance(v, str) for v in flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert contain_image_reference(flow_result.run_info)
        for _, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert contain_image_reference(node_run_info)

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs", get_test_cases_for_node_run()
    )
    def test_executor_exec_node_with_image(
        self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections
    ):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            storage=storage,
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert contain_image_reference(run_info)

    # Assert image could be persisted to the specified path.
    @pytest.mark.parametrize(
        "output_sub_dir, assign_storage, expected_path",
        [
            ("test_path", True, "test_storage"),
            ("test_path", False, "test_path"),
            (None, True, "test_storage"),
            (None, False, "."),
        ],
    )
    def test_executor_exec_node_with_image_storage_and_path(self, output_sub_dir, assign_storage, expected_path):
        flow_folder = SIMPLE_IMAGE_FLOW
        node_name = "python_node"
        image = {"data:image/jpg;path": str(get_flow_folder(SIMPLE_IMAGE_FLOW) / "logo.jpg")}
        flow_inputs = {"image": image}
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./test_storage"))
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=None,
            connections=None,
            storage=storage if assign_storage else None,
            output_sub_dir=output_sub_dir,
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert contain_image_reference(run_info, parent_path=expected_path)

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs",
        [
            (
                SIMPLE_IMAGE_WITH_INVALID_DEFAULT_VALUE_FLOW,
                "python_node_2",
                {},
                {
                    "python_node": {
                        "data:image/jpg;path": str(
                            get_flow_folder(SIMPLE_IMAGE_WITH_INVALID_DEFAULT_VALUE_FLOW) / "logo.jpg"
                        )
                    }
                },
            )
        ],
    )
    def test_executor_exec_node_with_invalid_default_value(
        self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections
    ):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            storage=storage,
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert contain_image_reference(run_info)

    @pytest.mark.parametrize(
        "flow_folder, inputs",
        get_test_cases_for_simple_input(EVAL_FLOW_WITH_SIMPLE_IMAGE)
        + get_test_cases_for_composite_input(EVAL_FLOW_WITH_COMPOSITE_IMAGE),
    )
    def test_executor_exec_aggregation_with_image(self, flow_folder, inputs, dev_connections):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, storage=storage)
        flow_result = executor.exec_line(inputs, index=0)
        flow_inputs = {k: [v] for k, v in inputs.items()}
        aggregation_inputs = {k: [v] for k, v in flow_result.aggregation_inputs.items()}
        aggregation_results = executor.exec_aggregation(flow_inputs, aggregation_inputs=aggregation_inputs)
        for _, node_run_info in aggregation_results.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert contain_image_reference(node_run_info)


def get_test_cases_for_openai_vision_input(flow_folder):
    working_dir = get_flow_folder(flow_folder)
    image = ImageProcessor.create_image_from_file(working_dir / "logo.jpg")
    inputs = [
        {"type": "image_file", "image_file": {"path": str(working_dir / "logo.jpg")}},
        {"type": "image_url", "image_url": {"url": image.to_base64(with_type=True)}},
        {"type": "image_url", "image_url": {"url": IMAGE_URL}},
        str(working_dir / "logo.jpg"),
        image.to_base64(),
        IMAGE_URL,
    ]
    return [(flow_folder, {"image": input}) for input in inputs]


def get_test_cases_for_openai_vision_node_run():
    image = {
        "type": "image_file",
        "image_file": {"path": str(get_flow_folder(SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE) / "logo.jpg")},
    }
    simple_image_input = {"image": image}

    return [
        (SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE, "python_node", simple_image_input, None),
        (SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE, "python_node_2", simple_image_input, {"python_node": image}),
    ]


@pytest.mark.usefixtures("dev_connections")
@pytest.mark.e2etest
class TestExecutorWithOpenaiVisionImage:
    @pytest.mark.parametrize(
        "flow_folder, inputs",
        get_test_cases_for_openai_vision_input(SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE)
        + [(CHAT_FLOW_WITH_OPENAI_VISION_IMAGE, {})],
    )
    def test_executor_exec_line_with_image(self, flow_folder, inputs, dev_connections):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        executor = FlowExecutor.create(get_yaml_file(flow_folder), dev_connections, storage=storage)
        flow_result = executor.exec_line(inputs)

        multimedia_processor = OpenaiVisionMultimediaProcessor()
        assert isinstance(flow_result.output, dict)
        assert contain_image_object(flow_result.output, multimedia_processor=multimedia_processor)
        # Assert output also contains plain text.
        assert any(isinstance(v, str) for v in flow_result.output)
        assert flow_result.run_info.status == Status.Completed
        assert contain_image_reference(flow_result.run_info, multimedia_processor=multimedia_processor)
        for _, node_run_info in flow_result.node_run_infos.items():
            assert node_run_info.status == Status.Completed
            assert contain_image_reference(node_run_info, multimedia_processor=multimedia_processor)

    @pytest.mark.parametrize(
        "flow_folder, node_name, flow_inputs, dependency_nodes_outputs",
        get_test_cases_for_openai_vision_node_run(),
    )
    def test_executor_exec_node_with_image(
        self, flow_folder, node_name, flow_inputs, dependency_nodes_outputs, dev_connections
    ):
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./temp"))
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=dependency_nodes_outputs,
            connections=dev_connections,
            storage=storage,
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert contain_image_reference(run_info, multimedia_processor=OpenaiVisionMultimediaProcessor())

    # Assert image could be persisted to the specified path.
    @pytest.mark.parametrize(
        "output_sub_dir, assign_storage, expected_path",
        [
            ("test_path", True, "test_storage"),
            ("test_path", False, "test_path"),
            (None, True, "test_storage"),
            (None, False, "."),
        ],
    )
    def test_executor_exec_node_with_image_storage_and_path(self, output_sub_dir, assign_storage, expected_path):
        flow_folder = SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE
        node_name = "python_node"
        image = {
            "type": "image_file",
            "image_file": {"path": str(get_flow_folder(SAMPLE_IMAGE_FLOW_WITH_OPENAI_VISION_IMAGE) / "logo.jpg")},
        }
        flow_inputs = {"image": image}
        working_dir = get_flow_folder(flow_folder)
        os.chdir(working_dir)
        storage = DefaultRunStorage(base_dir=working_dir, sub_dir=Path("./test_storage"))
        run_info = FlowExecutor.load_and_exec_node(
            get_yaml_file(flow_folder),
            node_name,
            flow_inputs=flow_inputs,
            dependency_nodes_outputs=None,
            connections=None,
            storage=storage if assign_storage else None,
            output_sub_dir=output_sub_dir,
            raise_ex=True,
        )
        assert run_info.status == Status.Completed
        assert contain_image_reference(
            run_info, parent_path=expected_path, multimedia_processor=OpenaiVisionMultimediaProcessor()
        )
