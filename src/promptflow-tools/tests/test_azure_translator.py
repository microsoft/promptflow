import json
import pytest

from promptflow.connections import CustomConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools import get_translation

import tests.utils as utils


@pytest.fixture
def translate_connection() -> CustomConnection:
    return ConnectionManager().get("translate_connection")


@pytest.mark.usefixtures("use_secrets_config_file")
class TestAzureTranslator:
    def test_translate(self, translate_connection):
        input_text = "This is a long sentence that I want to translate."
        result = get_translation(
            translate_connection, input_text, source_language="en", target_language="fr")
        # builtin tool output should be json serializable
        # make sure to run successfully in single node run mode.
        utils.is_json_serializable(result, "translate()")
        print(f"translate() :{json.dumps(result)}")
        assert result is not None and "Exception" not in result
