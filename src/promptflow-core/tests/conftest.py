import json
from unittest.mock import patch

import pytest

from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider

from ._constants import CONNECTION_FILE


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
