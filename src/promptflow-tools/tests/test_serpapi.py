import pytest

from promptflow.exceptions import UserErrorException
from promptflow.tools.serpapi import Engine, SafeMode, search

import tests.utils as utils


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip_if_no_key("serp_connection")
class TestSerpAPI:
    def test_engine(self, serp_connection):
        query = "cute cats"
        num = 2
        result_dict = search(
            connection=serp_connection, query=query, num=num, safe=SafeMode.ACTIVE, engine=Engine.GOOGLE.value)
        utils.is_json_serializable(result_dict, "serp api search()")
        assert result_dict["search_metadata"]["google_url"] is not None
        assert int(result_dict["search_parameters"]["num"]) == num
        assert result_dict["search_parameters"]["safe"].lower() == "active"

        result_dict = search(
            connection=serp_connection, query=query, num=num, safe=SafeMode.ACTIVE, engine=Engine.BING.value)
        utils.is_json_serializable(result_dict, "serp api search()")
        assert int(result_dict["search_parameters"]["count"]) == num
        assert result_dict["search_parameters"]["safe_search"].lower() == "strict"

    def test_invalid_api_key(self, serpapi_connection):
        serpapi_connection.api_key = "hello"
        query = "cute cats"
        num = 2
        engine = Engine.GOOGLE.value
        error_msg = "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_connection, query=query, num=num, engine=engine)
        assert error_msg == exc_info.value.args[0]

    @pytest.mark.parametrize("engine", [Engine.GOOGLE.value, Engine.BING.value])
    def test_invalid_query(self, serpapi_connection, engine):
        query = ""
        num = 2
        error_msg = "Missing query `q` parameter."
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_connection, query=query, num=num, engine=engine)
        assert error_msg == exc_info.value.args[0]
