import json
import unittest
from pathlib import Path

import pytest

from promptflow.connections import CustomConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.tools import AzureFormRecognizer

import tests.utils as utils

PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.fixture
def form_recognizer_connection() -> CustomConnection:
    return ConnectionManager().get("form_recognizer_connection")


@pytest.fixture
def form_recognizer_provider(form_recognizer_connection) -> AzureFormRecognizer:
    provider = AzureFormRecognizer(form_recognizer_connection)
    return provider


@pytest.mark.usefixtures("use_secrets_config_file", "form_recognizer_provider", "form_recognizer_connection")
class TestAzureFormRecognizer:
    def test_analyze_document(self, form_recognizer_provider):
        document_url = "https://raw.githubusercontent.com/Azure-Samples" + \
            "/cognitive-services-REST-api-samples/master/curl/form-recognizer/rest-api/layout.png"
        result = form_recognizer_provider.analyze_document(document_url)

        utils.is_json_serializable(result, "analyze_document()")
        print(f"analyze_document() :{json.dumps(result)}")
        assert result is not None and "Exception" not in result


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
