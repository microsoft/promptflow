import json
import unittest
from pathlib import Path

import pytest

from promptflow.connections import CustomConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools import AzureTranslator

import tests.utils as utils

PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.fixture
def translate_connection() -> CustomConnection:
    return ConnectionManager().get("translate_connection")


@pytest.fixture
def translate_provider(translate_connection) -> AzureTranslator:
    translateProvider = AzureTranslator(translate_connection)
    return translateProvider


@pytest.mark.usefixtures("use_secrets_config_file", "translate_provider", "translate_connection")
class TestAzureTranslator:
    def test_translate(self, translate_provider):
        input_text = "This is a long sentence that I want to translate."
        result = translate_provider.get_translation(input_text, source_language="en", target_language="fr")

        utils.is_json_serializable(result, "translate()")
        print(f"translate() :{json.dumps(result)}")
        assert result is not None and "Exception" not in result


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
