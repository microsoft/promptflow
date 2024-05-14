import json
from pathlib import Path
from typing import Union

import opentelemetry
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from promptflow._utils.flow_utils import resolve_flow_path

TEST_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests"
DATA_ROOT = TEST_ROOT / "test_configs/datas"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"
FLEX_FLOW_ROOT = TEST_ROOT / "test_configs/eager_flows"
WRONG_FLOW_ROOT = TEST_ROOT / "test_configs/wrong_flows"
ASSISTANT_DEFINITION_ROOT = TEST_ROOT / "test_configs/assistant_definitions"
PACKAGE_TOOL_ROOT = TEST_ROOT / "executor" / "package_tools"


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = None) -> Path:
    if file_name is None:
        flow_path, flow_file = resolve_flow_path(get_flow_folder(folder_name, root), check_flow_exist=False)
        yaml_file = flow_path / flow_file
    else:
        yaml_file = get_flow_folder(folder_name, root) / file_name

    return yaml_file


def get_flow_inputs_file(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.jsonl") -> Path:
    inputs_file = get_flow_folder(folder_name, root) / file_name
    return inputs_file


def get_flow_sample_input(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.jsonl"):
    inputs = load_jsonl(get_flow_inputs_file(folder_name, root, file_name))
    return inputs[0]


def get_flow_inputs(folder_name, root: str = FLOW_ROOT, file_name: str = "inputs.jsonl"):
    return load_jsonl(get_flow_inputs_file(folder_name, root, file_name))


def get_flow_expected_result(folder_name):
    samples_inputs = load_json(get_flow_folder(folder_name) / "expected_result.json")
    return samples_inputs


def get_flow_package_tool_definition(folder_name):
    return load_json(get_flow_folder(folder_name) / "package_tool_definition.json")


def load_json(source: Union[str, Path]) -> dict:
    """Load json file to dict"""
    with open(source, "r") as f:
        loaded_data = json.load(f)
    return loaded_data


def load_jsonl(source: Union[str, Path]) -> list:
    """Load jsonl file to list"""
    with open(source, "r") as f:
        loaded_data = [json.loads(line.strip()) for line in f]
    return loaded_data


def load_content(source: Union[str, Path]) -> str:
    """Load file content to string"""
    return Path(source).read_text()


def count_lines(filename):
    with open(filename, "r") as f:
        lines = f.readlines()
    return len(lines)


def is_image_file(file_path: Path):
    image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
    file_extension = file_path.suffix.lower()
    return file_extension in image_extensions


def prepare_memory_exporter():
    tracer_provider = TracerProvider()
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    tracer_provider.add_span_processor(span_processor)
    opentelemetry.trace.set_tracer_provider(tracer_provider)
    return memory_exporter
