import json

import pytest
from pytest_mock import MockerFixture  # noqa: E402
from requests import Response

from promptflow.core.connection_manager import ConnectionManager
from promptflow.exceptions import SystemErrorException, UserErrorException
from promptflow.tools.bing import Bing
from promptflow.connections import BingConnection


@pytest.fixture
def bing_config() -> BingConnection:
    return ConnectionManager().get("bing_config")


@pytest.fixture
def bing_provider(bing_config) -> Bing:
    bingProvider = Bing.from_config(bing_config)
    return bingProvider


@pytest.mark.unittest
@pytest.mark.usefixtures("use_secrets_config_file", "bing_provider", "bing_config")
class TestBing:
    def test_write_record_to_blob(self, basic_executor, mocker: MockerFixture) -> None:
        """Test write flow/node records to remote azure blob."""
        # mock the limit data to a lower value
        mocker.patch("promptflow.storage.azureml_run_storage.TABLE_LIMIT_PROPERTY_SIZE", 10)

    def test_extract_error_message_and_code(self, bing_provider):
        error_code_reference = (
            "For more info, please refer to "
            "https://learn.microsoft.com/en-us/bing/search-apis/"
            "bing-web-search/reference/error-codes"
        )

        error_json = {"hello": "world"}
        res = bing_provider.extract_error_message_and_code(error_json)
        assert len(res) == 0

        message_value = "message value"
        error_json = {"message": message_value}
        res = bing_provider.extract_error_message_and_code(error_json)
        assert res == message_value

        code_value = "code value"
        error_json = {"message": message_value, "code": code_value}
        res = bing_provider.extract_error_message_and_code(error_json)
        assert res == message_value + " " + f"code: {code_value}. {error_code_reference}"

        error_json = {}
        res = bing_provider.extract_error_message_and_code(error_json)
        assert len(res) == 0

        error_json = None
        res = bing_provider.extract_error_message_and_code(error_json)
        assert len(res) == 0

    def test_extract_error_message(self, bing_provider):
        error_json = {"hello": "world"}
        res = bing_provider.extract_error_message(error_json)
        assert len(res) == 0

        error_json = {"error": {"message": "error value"}}
        res = bing_provider.extract_error_message(error_json)
        assert res == bing_provider.extract_error_message_and_code(error_json["error"])

        error_json = {"error": {"message": "error value", "code": "code value"}, "errors": None}
        res = bing_provider.extract_error_message(error_json)
        assert res == bing_provider.extract_error_message_and_code(error_json["error"])

        error_json = {
            "error": {"message": "error value", "code": "code value"},
            "errors": [{"message": "error value1", "code": "code value1"}],
        }
        res = bing_provider.extract_error_message(error_json)
        assert res == bing_provider.extract_error_message_and_code(error_json["errors"][0])

    def test_search_unexpected_error(self, bing_provider, mocker: MockerFixture):
        dummyEx = Exception("Something went wrong")
        mocker.patch("requests.get", side_effect=dummyEx)
        with pytest.raises(SystemErrorException) as exc_info:
            bing_provider.search(query="best shop in beijing", count=1)
        assert "Unexpected exception occurs. Please check logs for details." == exc_info.value.args[0]
        assert dummyEx.args[0] != exc_info.value.args[0]

    def test_search_unexpected_error_while_extract_error_messsage_from_response(
        self, bing_provider, mocker: MockerFixture
    ):
        default_error_message = "Bing search request failed. Please check logs for details."
        dummyEx = Exception("Something went wrong")

        response = Response()
        response.status_code = 400
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps({"key1": "value1", "key2": "value2"}).encode()

        mocker.patch("requests.get", return_value=response)
        mocker.patch("promptflow.tools.bing.Bing.extract_error_message", side_effect=dummyEx)

        with pytest.raises(UserErrorException) as exc_info:
            bing_provider.search(query="best shop in beijing", count=1)
        assert default_error_message == exc_info.value.args[0]
        assert dummyEx.args[0] != exc_info.value.args[0]

        # change to system error code
        response.status_code = 502
        with pytest.raises(SystemErrorException) as exc_info:
            bing_provider.search(query="best shop in beijing", count=1)
        assert default_error_message == exc_info.value.args[0]
        assert dummyEx.args[0] != exc_info.value.args[0]
