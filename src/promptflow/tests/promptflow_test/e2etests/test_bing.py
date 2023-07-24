import json
import unittest
from pathlib import Path

import pytest

from promptflow.core.connection_manager import ConnectionManager
from promptflow.exceptions import UserErrorException
from promptflow.tools import Bing
from promptflow.connections import BingConnection

PROMOTFLOW_ROOT = Path(__file__) / "../../../../"


@pytest.fixture
def bing_config() -> BingConnection:
    return ConnectionManager().get("bing_config")


@pytest.fixture
def bing_provider(bing_config) -> Bing:
    bingProvider = Bing.from_config(bing_config)
    return bingProvider


@pytest.mark.usefixtures("use_secrets_config_file", "bing_provider", "bing_config")
@pytest.mark.e2etest
@pytest.mark.flaky(reruns=5, reruns_delay=1)
class TestBing:
    def test_bing_search_count_offset(self, bing_provider):
        query = "sailing dinghies site"
        count = 3  # size of query result, this only impact default answer, not promote answer
        offset = 0
        result_dict = bing_provider.search(query=query, count=count, offset=offset)
        print("bing.search() count first 3 result:\n" + json.dumps(result_dict))
        assert len(result_dict["webPages"]["value"]) == count

        # retrive the next 3 records
        offset = 3
        result_dict = bing_provider.search(query=query, count=count, offset=offset)
        print("bing.search() count next 3 result:\n" + json.dumps(result_dict))
        assert len(result_dict["webPages"]["value"]) == count

    def test_bing_search_answerCount(self, bing_provider):
        query = "sailing dinghies site"
        count = 2  # size of query result, this only impact default answer, not promote answer
        answerCount = 1  # answers size

        result_dict = bing_provider.search(query=query, count=count, answerCount=answerCount)
        print("bing.search() answerCount result1:\n" + json.dumps(result_dict))
        assert len(result_dict["webPages"]["value"]) == count
        assert result_dict.get("images") is None
        assert result_dict.get("relatedSearches") is None

        # To include more answercounts
        answerCount = 5
        result_dict = bing_provider.search(query=query, count=count, answerCount=answerCount)
        print("bing.search() answerCount result2:\n" + json.dumps(result_dict))
        assert len(result_dict["webPages"]["value"]) == count
        assert result_dict["relatedSearches"] is not None

    def test_bing_search_responseFilter(self, bing_provider):
        query = "cute puppies"
        count = 1  # size of query result, this only impact default answer, not promote answer
        answerCount = 5  # answers size
        promote = json.dumps(["Webpages", "Images"])

        # Test ResponseFilter, No filter
        # Note: we must provide responseFilter here. If without, the return would be webpages + searchRelevance.
        responseFilter = json.dumps(["Webpages", "Images"])
        # bing api response is limited to responseFilter but may not be the same.
        # For example, images may not be returned.
        result_dict = bing_provider.search(
            query=query, answerCount=answerCount, count=count, promote=promote, responseFilter=responseFilter
        )
        print("bing.search() responseFilter1 result:\n" + json.dumps(result_dict))
        if result_dict.get("webpages") is None:
            assert len(result_dict["webPages"]["value"]) == count

        # Filter only images
        responseFilter = json.dumps(["Images"])
        result_dict = bing_provider.search(
            query=query, answerCount=answerCount, count=count, promote=promote, responseFilter=responseFilter
        )
        print("bing.search() responseFilter2 result:\n" + json.dumps(result_dict))
        assert result_dict.get("webpages") is None

    def test_bing_api_search_wrong_responseFilter(self, bing_config):
        query = "cute puppies"
        count = 4  # size of query result, this only impact default answer, not promote answer
        answerCount = 5  # answers size
        promote = json.dumps(["Webpages", "Images"])

        # Test ResponseFilter, No filter
        # Note: we must provide responseFilter here. If without, the return would be webpages + searchRelevance.
        responseFilter = json.dumps(["Webpages", "hello"])

        with pytest.raises(UserErrorException) as exc_info:
            Bing.from_config(bing_config).search(
                query=query, answerCount=answerCount, count=count, promote=promote, responseFilter=responseFilter
            )
        assert (
            "Insufficient authorization to access requested resource. code: InsufficientAuthorization. "
            "For more info, please refer to "
            "https://learn.microsoft.com/"
            "en-us/bing/search-apis/bing-web-search/reference/error-codes" == exc_info.value.args[0]
        )

    def test_bing_api_non_200_status_code(self, bing_config):
        # change to be invlaid api_key
        bing_config.api_key = "sfsfs"
        query = "cute puppies"
        count = 1
        with pytest.raises(UserErrorException) as exc_info:
            Bing.from_config(bing_config).search(query=query, count=count)

        assert (
            "Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid "
            "key for an active subscription and use a correct regional API endpoint for your resource. "
            "code: 401. For more info, please refer to "
            "https://learn.microsoft.com/en-us/bing/search-apis/"
            "bing-web-search/reference/error-codes" == exc_info.value.args[0]
        )


# Run the unit tests
if __name__ == "__main__":
    unittest.main()
