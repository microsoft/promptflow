import json
from pathlib import Path

import pytest


@pytest.fixture
def dev_connections() -> dict:
    with open(
        file=(Path(__file__).parent.parent / "connections.json").resolve().absolute().as_posix(),
        mode="r",
    ) as f:
        return json.load(f)
