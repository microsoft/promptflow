import datetime

import pytest

from promptflow.azure._storage.blob.client import _get_datastore_client_key, _get_datastore_from_map, datastore_map


@pytest.mark.unittest
class TestCosmosDB:
    def test_get_datastore_from_map(self):
        datastore_map["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(0, -1),  # already expire
            "datastore": "test",
        }
        assert _get_datastore_from_map("test") is None

        datastore_map["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(1, 0),  # expire after 1 day
            "datastore": "test",
        }
        assert _get_datastore_from_map("test") == "test"

    def test_get_datastore_client_key(self):
        assert _get_datastore_client_key("sub", "rg", "ws") == "sub@rg@ws"
