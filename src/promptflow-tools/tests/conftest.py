import json
import os
import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture  # noqa: E402

from promptflow._constants import PROMPTFLOW_CONNECTIONS

PROMOTFLOW_ROOT = Path(__file__) / "../.."
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
root_str = str(PROMOTFLOW_ROOT.resolve().absolute())
if root_str not in sys.path:
    sys.path.insert(0, root_str)


PROMOTFLOW_ROOT = Path(__file__).absolute().parents[1]


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


@pytest.fixture
def example_prompt_template() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/prompt.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def chat_history() -> list:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/history.json") as f:
        history = json.load(f)
    return history


@pytest.fixture
def example_prompt_template_with_function() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_function.jinja2") as f:
        prompt_template = f.read()
    return prompt_template
