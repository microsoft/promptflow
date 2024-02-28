import datetime

import pytest

from promptflow.azure._storage.cosmosdb.client import _get_client_from_map, client_map


@pytest.mark.unittest
class TestCosmosDB:
    def test_get_client_from_map(self):
        client_map["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(0, -1),  # already expire
            "client": "test",
        }
        assert _get_client_from_map("test") is None

        client_map["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(1, 0),  # expire after 1 day
            "client": "test",
        }
        assert _get_client_from_map("test") == "test"
