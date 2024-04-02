import json

import pytest

from ._constants import CONNECTION_FILE


@pytest.fixture
def dev_connections() -> dict:
    with open(CONNECTION_FILE, "r") as f:
        return json.load(f)
