import json
from pathlib import Path
from typing import Dict, Union

import opentelemetry.trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = "flow.dag.yaml") -> Path:
    yaml_file = get_flow_folder(folder_name, root) / file_name
    return yaml_file


def get_flow_sample_inputs(folder_name, root: str = FLOW_ROOT, sample_inputs_file="samples.json"):
    samples_inputs = load_json(get_flow_folder(folder_name, root) / sample_inputs_file)
    return samples_inputs


def get_flow_configs(folder_name, root: str = FLOW_ROOT, file_name: str = "configs.json") -> Dict:
    configs_file = get_flow_folder(folder_name, root) / file_name
    return load_json(configs_file)


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


def prepare_memory_exporter():
    tracer_provider = TracerProvider()
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    tracer_provider.add_span_processor(span_processor)
    otel_trace.set_tracer_provider(tracer_provider)
    return memory_exporter
