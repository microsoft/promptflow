import json
from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._utils.flow_utils import resolve_flow_path
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider

TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"
PROMPTY_FLOW_ROOT = TEST_CONFIG_ROOT / "prompty"
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


@pytest.fixture
def mock_dict_azure_open_ai_connection(dev_connections):
    connection = dev_connections["azure_open_ai_connection"]
    # TODO(3128519): Remove this after the connection type is added to github secrets
    if "type" not in connection:
        connection["type"] = "AzureOpenAIConnection"

    with patch(
        "promptflow.connections.ConnectionProvider.get_instance",
        return_value=DictConnectionProvider({"azure_open_ai_connection": connection}),
    ):
        yield
