from pathlib import Path

from promptflow._utils.flow_utils import resolve_flow_path

TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_path, flow_file = resolve_flow_path(get_flow_folder(folder_name, root), check_flow_exist=False)
    yaml_file = flow_path / flow_file
    return yaml_file
