import json
from pathlib import Path
from typing import Union

TEST_ROOT = Path(__file__).parent.parent
DATA_ROOT = TEST_ROOT / "test_configs/datas"
FLOW_ROOT = TEST_ROOT / "test_configs/flows"
WRONG_FLOW_ROOT = TEST_ROOT / "test_configs/wrong_flows"


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = "flow.dag.yaml"):
    flow_folder_path = Path(root) / folder_name
    yaml_file = flow_folder_path / file_name
    return yaml_file


def get_flow_inputs(folder_name, root: str = FLOW_ROOT):
    flow_folder_path = Path(root) / folder_name
    inputs = load_json(flow_folder_path / "inputs.json")
    return inputs[0] if isinstance(inputs, list) else inputs


def get_bulk_inputs(folder_name):
    flow_folder_path = Path(FLOW_ROOT) / folder_name
    inputs = load_json(flow_folder_path / "inputs.json")
    return [inputs] if isinstance(inputs, dict) else inputs


def get_flow_sample_inputs(folder_name, root: str = FLOW_ROOT, sample_inputs_file="samples.json"):
    flow_folder_path = Path(root) / folder_name
    samples_inputs = load_json(flow_folder_path / sample_inputs_file)
    return samples_inputs


def get_flow_expected_metrics(folder_name):
    flow_folder_path = Path(FLOW_ROOT) / folder_name
    samples_inputs = load_json(flow_folder_path / "expected_metrics.json")
    return samples_inputs


def get_flow_expected_status_summary(folder_name):
    flow_folder_path = Path(FLOW_ROOT) / folder_name
    samples_inputs = load_json(flow_folder_path / "expected_status_summary.json")
    return samples_inputs


def get_flow_expected_result(folder_name):
    flow_folder_path = Path(FLOW_ROOT) / folder_name
    samples_inputs = load_json(flow_folder_path / "expected_result.json")
    return samples_inputs


def get_flow_package_tool_definition(folder_name):
    flow_folder_path = Path(FLOW_ROOT) / folder_name
    return load_json(flow_folder_path / "package_tool_definition.json")


def load_json(source: Union[str, Path]) -> dict:
    """Load json file to dict"""
    with open(source, "r") as f:
        loaded_data = json.load(f)
    return loaded_data


def load_content(source: Union[str, Path]) -> str:
    """Load file content to string"""
    return Path(source).read_text()
