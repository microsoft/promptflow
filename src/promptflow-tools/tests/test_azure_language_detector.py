import json
import unittest
from pathlib import Path

import pytest

from promptflow.connections import CustomConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools import AzureDetect

import tests.utils as utils

PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.fixture
def translate_connection() -> CustomConnection:
    return ConnectionManager().get("translate_connection")


@pytest.fixture
def detect_provider(translate_connection) -> AzureDetect:
    translateProvider = AzureDetect(translate_connection)
    return translateProvider


@pytest.mark.usefixtures("use_secrets_config_file", "detect_provider", "translate_connection")
class TestAzureLanguageDetector:
    def test_detect(self, detect_provider):
        input_text = "This is a long sentence that I want to translate."
        result = detect_provider.get_language(input_text)

        utils.is_json_serializable(result, "detect()")
        print(f"detect() :{json.dumps(result)}")
        assert result == "en"


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
