import json
from pathlib import Path

import pytest

from promptflow._utils.flow_utils import resolve_flow_path

TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"
CONNECTION_FILE = Path(__file__).parent.parent / "connections.json"


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


@pytest.fixture
def dev_connections() -> dict:
    with open(CONNECTION_FILE, "r") as f:
        return json.load(f)
