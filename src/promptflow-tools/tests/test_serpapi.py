import json
from pathlib import Path

import pytest

from promptflow.connections import SerpConnection
from promptflow.core.connection_manager import ConnectionManager
from promptflow.exceptions import UserErrorException
from promptflow.tools.serpapi import Engine, SafeMode, SerpAPI, search

import tests.utils as utils

PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.fixture
def serpapi_config() -> SerpConnection:
    return ConnectionManager().get("serp_connection")


@pytest.fixture
def serpapi_provider(serpapi_config) -> SerpAPI:
    serpAPIProvider = SerpAPI.from_config(serpapi_config)
    return serpAPIProvider


@pytest.mark.usefixtures("use_secrets_config_file", "serpapi_provider", "serpapi_config")
@pytest.mark.skip(reason="serpapi key not set yet")
class TestSerpAPI:
    def test_start_num_ijn(self, serpapi_provider):
        query = "Cute cat"
        num = 3
        result_dict = serpapi_provider.search(query=query, num=num, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_start_num_ijn result1:\n" + json.dumps(result_dict))
        assert len(result_dict["organic_results"]) <= num

        start = 10
        result_dict = serpapi_provider.search(query=query, num=num, start=start, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_start_num_ijn result2:\n" + json.dumps(result_dict))
        assert int(result_dict["search_parameters"]["start"]) == start
        assert result_dict["search_parameters"].get("ijn") is None
        assert "ijn=" not in result_dict["search_metadata"]["google_url"]

        ijn = 5
        result_dict = serpapi_provider.search(query=query, num=num, ijn=ijn, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_start_num_ijn result3:\n" + json.dumps(result_dict))
        assert int(result_dict["search_parameters"]["num"]) == num
        # ijn value will be ignore if start not specified
        assert result_dict["search_parameters"].get("start") is None
        assert result_dict["search_parameters"].get("ijn") is None

        ijn = 5
        tbm = "isch"
        result_dict = serpapi_provider.search(query=query, num=num, start=start, ijn=ijn, tbm=tbm, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_start_num_ijn result4:\n" + json.dumps(result_dict))
        assert int(result_dict["search_parameters"]["start"]) == start
        # ijn value will be ignore if start not specified
        assert int(result_dict["search_parameters"]["ijn"]) == ijn
        assert int(result_dict["search_parameters"]["num"]) == num
        assert f"ijn={ijn}" in result_dict["search_metadata"]["google_url"]
        assert f"num={num}" in result_dict["search_metadata"]["google_url"]

    def test_tbm(self, serpapi_provider):
        query = "cute cats"
        num = 5

        tbm = "isch"
        result_dict = serpapi_provider.search(query=query, tbm=tbm, num=num, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_tbm result1:\n" + json.dumps(result_dict))
        assert result_dict["images_results"] is not None
        # we could not validate the num here; for "isch" the return num not match somewhow

        tbm = "vid"
        result_dict = serpapi_provider.search(query=query, tbm=tbm, num=num, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_tbm result2:\n" + json.dumps(result_dict))
        assert len(result_dict["video_results"]) <= num

        tbm = None
        result_dict = serpapi_provider.search(query=query, tbm=tbm, num=num, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_tbm result3:\n" + json.dumps(result_dict))
        assert len(result_dict["organic_results"]) <= num

    def test_output(self, serpapi_provider):
        query = "cute cats"

        result_dict = serpapi_provider.search(query=query, num=2, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_output result1:\n" + json.dumps(result_dict))
        assert "<!doctype html>" not in result_dict

        output = "HTML"
        result_dict = serpapi_provider.search(query=query, num=2, output=output, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_output result2:\n" + json.dumps(result_dict))
        assert "<!doctype html>" in result_dict

    def test_location_gl(self, serpapi_provider):
        query = "cute cats"
        location = ("Texas,Austin",)

        result_dict = serpapi_provider.search(query=query, num=2, location=location, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_location_gl result1:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["location_requested"] in location

        gl = "uk"
        result_dict = serpapi_provider.search(query=query, num=2, gl=gl, location=location, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_location_gl result2:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["location_requested"] in location
        assert result_dict["search_parameters"]["gl"] == gl

    def test_domain(self, serpapi_provider):
        query = "Cute cat"

        google_domain = None
        result_dict = serpapi_provider.search(query=query, google_domain=google_domain, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_domain result1:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["google_domain"] == "google.com"

        google_domain = "google.al"
        result_dict = serpapi_provider.search(query=query, google_domain=google_domain, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_domain result2:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["google_domain"] == google_domain

        # this spec would be ignored if engine is not google
        google_domain = "google.al"
        result_dict = serpapi_provider.search(query=query, google_domain=google_domain, engine="bing")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_domain result3:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"].get("google_domain") is None

    def test_tbs(self, serpapi_provider):
        query = "cute cats"

        tbs = "dur:l"
        result_dict = serpapi_provider.search(query=query, num=2, tbs=tbs, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_location_gl result1:\n" + json.dumps(result_dict))
        assert tbs == result_dict["search_parameters"]["tbs"]

    def test_safe(self, serpapi_provider):
        query = "I am looking for tools to hurt animals"

        safe = SafeMode.ACTIVE
        result_dict = serpapi_provider.search(query=query, num=2, safe=safe, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_safe result1:\n" + json.dumps(result_dict))
        assert safe == result_dict["search_parameters"]["safe"]

        safe = None
        result_dict = serpapi_provider.search(query=query, num=2, safe=safe, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_safe result12\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"].get("safe") is None

        # google is tolerant to bad safe input
        safe = "None"
        result_dict = serpapi_provider.search(query=query, num=2, safe=safe, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_safe result3\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"].get("safe") is None

    def test_nfpr_filter(self, serpapi_provider):
        query = "cute cats"

        nfpr = True
        filter = "videos"
        result_dict = serpapi_provider.search(query=query, num=2, nfpr=nfpr, filter=filter, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_nfpr_filter result1:\n" + json.dumps(result_dict))
        assert str(nfpr) == result_dict["search_parameters"]["nfpr"]
        assert filter == result_dict["search_parameters"]["filter"]

        nfpr = False
        filter = "videos"
        result_dict = serpapi_provider.search(query=query, num=2, nfpr=nfpr, filter=filter, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_nfpr_filter result2:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"].get("nfpr") is None
        assert filter == result_dict["search_parameters"]["filter"]

    def test_device(self, serpapi_provider):
        query = "cute cats"

        result_dict = serpapi_provider.search(query=query, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_device result1:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["device"] == "desktop"

        device = "mobile"
        result_dict = serpapi_provider.search(query=query, device=device, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_device result1:\n" + json.dumps(result_dict))
        assert result_dict["search_parameters"]["device"] == device

    def test_cache_asynch(self, serpapi_provider):
        query = "cute cats"

        no_cache = True
        asynch = False
        result_dict = serpapi_provider.search(query=query, no_cache=no_cache, asynch=asynch, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_cache_asynch result1:\n" + json.dumps(result_dict))
        assert result_dict["search_information"] is not None

        no_cache = True
        asynch = True
        result_dict = serpapi_provider.search(query=query, no_cache=no_cache, asynch=asynch, engine="google")
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_cache_asynch result2:\n" + json.dumps(result_dict))
        # no_cache and async could not be True at the same time
        assert result_dict.get("search_information") is None

    def test_engine(self, serpapi_provider):
        query = "cute cats"
        num = 2
        engine = Engine.GOOGLE.value
        result_dict = serpapi_provider.search(query=query, num=num, safe=SafeMode.ACTIVE, engine=engine)
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_engine result1:\n" + json.dumps(result_dict))
        assert result_dict["search_metadata"]["google_url"] is not None
        assert int(result_dict["search_parameters"]["num"]) == num
        assert result_dict["search_parameters"]["safe"].lower() == "active"

        engine = Engine.BING.value
        result_dict = serpapi_provider.search(query=query, num=num, safe=SafeMode.ACTIVE, engine=engine)
        utils.is_json_serializable(result_dict, "Serp_API.search()")
        print("test_engine result2:\n" + json.dumps(result_dict))
        assert int(result_dict["search_parameters"]["count"]) == num
        assert result_dict["search_parameters"]["safe_search"].lower() == "strict"

    def test_invalid_api_key(self, serpapi_config):
        serpapi_config.api_key = "hello"
        query = "cute cats"
        num = 2
        engine = Engine.GOOGLE.value
        error_msg = "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_config, query=query, num=num, engine=engine)
        assert error_msg == exc_info.value.args[0]

    def test_invalid_query_for_google(self, serpapi_config):
        query = ""
        num = 2
        engine = Engine.GOOGLE.value
        error_msg = "Missing query `q` parameter."
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_config, query=query, num=num, engine=engine)
        assert error_msg == exc_info.value.args[0]

    def test_invalid_query_for_bing(self, serpapi_config):
        query = ""
        num = 2
        engine = Engine.BING.value
        error_msg = "Missing query `q` parameter."
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_config, query=query, num=num, engine=engine)
        assert error_msg == exc_info.value.args[0]

    def test_invalid_api_key_for_html_output(self, serpapi_config):
        serpapi_config.api_key = "hello"
        query = "cute cats"
        num = 2
        engine = Engine.GOOGLE.value
        output = "html"
        error_msg = "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"
        with pytest.raises(UserErrorException) as exc_info:
            search(connection=serpapi_config, query=query, num=num, engine=engine, output=output)
        assert error_msg == exc_info.value.args[0]
