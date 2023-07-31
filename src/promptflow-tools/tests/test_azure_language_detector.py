import json
import pytest

from promptflow.connections import CustomConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools import get_language

import tests.utils as utils


@pytest.fixture
def translate_connection() -> CustomConnection:
    return ConnectionManager().get("translate_connection")


def test_get_language(translate_connection):
    input_text = "This is a long sentence that I want to translate."
    result = get_language(translate_connection, input_text)
    # builtin tool output should be json serializable
    # make sure to run successfully in single node run mode.
    utils.is_json_serializable(result, "detect()")
    print(f"detect() :{json.dumps(result)}")
    assert result == "en"
