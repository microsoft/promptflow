from pathlib import Path

TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = "flow.dag.yaml") -> Path:
    yaml_file = get_flow_folder(folder_name, root) / file_name
    return yaml_file
