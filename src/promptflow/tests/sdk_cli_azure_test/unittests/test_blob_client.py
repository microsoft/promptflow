import datetime

import pytest

from promptflow.azure._storage.blob.client import _datastore_cache, _get_datastore_client_key, _get_datastore_from_cache


@pytest.mark.unittest
class TestBlobClient:
    def test_get_datastore_from_cache(self):
        _datastore_cache["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(0, -1),  # already expire
            "datastore": "test",
        }
        assert _get_datastore_from_cache("test") is None

        _datastore_cache["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(1, 0),  # expire after 1 day
            "datastore": "test",
        }
        assert _get_datastore_from_cache("test") == "test"

    def test_get_datastore_client_key(self):
        assert _get_datastore_client_key("sub", "rg", "ws") == "sub@rg@ws"
