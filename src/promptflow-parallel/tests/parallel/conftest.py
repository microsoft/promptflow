# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest


@pytest.fixture
def promptflow_root_dir():
    return Path(__file__).parent.parent.parent.parent / "promptflow"


@pytest.fixture
def test_config_dir(promptflow_root_dir):
    return promptflow_root_dir / "tests" / "test_configs"


@pytest.fixture
def flow_dir(test_config_dir):
    return test_config_dir / "flows"
