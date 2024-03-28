import datetime

import pytest

from promptflow.azure._storage.cosmosdb.client import (
    _get_client_from_map,
    _get_container_lock,
    _get_db_client_key,
    client_map,
)


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

    def test_get_container_lock(self):
        container_lock = _get_container_lock("test")
        assert container_lock is not None
        assert _get_container_lock("test2") != container_lock
        assert _get_container_lock("test") == container_lock

    def test_get_db_client_key(self):
        assert _get_db_client_key("container", "sub", "rg", "ws") == "sub@rg@ws@container"
