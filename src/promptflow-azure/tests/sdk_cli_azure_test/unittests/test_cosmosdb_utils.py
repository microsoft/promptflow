from dataclasses import dataclass
from unittest import mock

import pytest
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError

from promptflow.azure._storage.cosmosdb.cosmosdb_utils import safe_create_cosmosdb_item


@dataclass
class Item:
    id: str
    partition_key: str


@pytest.mark.unittest
class TestCosmosDBUtils:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.item = Item(id="id", partition_key="partition_key")

    def test_safe_write_to_cosmosdb_normal(self):
        client = mock.Mock()
        client.read_item.side_effect = CosmosResourceNotFoundError

        safe_create_cosmosdb_item(client, self.item)

        client.read_item.assert_called_once_with(item=self.item.id, partition_key=self.item.partition_key)
        client.create_item.assert_called_once()

    def test_safe_write_to_cosmosdb_conflict(self):
        client = mock.Mock()
        client.read_item.side_effect = CosmosResourceNotFoundError
        client.create_item.side_effect = CosmosResourceExistsError

        safe_create_cosmosdb_item(client, self.item)

        client.read_item.assert_called_once_with(item=self.item.id, partition_key=self.item.partition_key)
        client.create_item.assert_called_once()

    def test_safe_write_to_cosmosdb_already_exist(self):
        client = mock.Mock()
        client.read_item.return_value = self.item

        safe_create_cosmosdb_item(client, self.item)

        client.read_item.assert_called_once_with(item=self.item.id, partition_key=self.item.partition_key)
        client.create_item.assert_not_called()
