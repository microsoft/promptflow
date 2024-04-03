from unittest import mock

import pytest

from promptflow._sdk._constants import CreatedByFieldName
from promptflow.azure._storage.cosmosdb.collection import CollectionCosmosDB


@pytest.mark.unittest
class TestCollectionCosmosDB:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.span = mock.Mock()
        self.span.attributes = dict()
        self.span.resource = {
            "attributes": {
                "collection.id": "test_collection_id",
                "collection": "test_collection_name",
            }
        }
        self.created_by = {CreatedByFieldName.OBJECT_ID: "test_user_id"}
        self.collection = CollectionCosmosDB(self.span, True, self.created_by)

    def test_collection_properties_cloud(self):
        collection = CollectionCosmosDB(self.span, True, self.created_by)
        assert collection.collection_name == "test_collection_name"
        assert collection.collection_id == "test_collection_id"
        assert collection.location == 1

        self.span.attributes = {"batch_run_id": "test_batch_run_id"}
        collection = CollectionCosmosDB(self.span, True, self.created_by)
        assert collection.collection_name == "test_collection_name"
        assert collection.collection_id == "test_batch_run_id"
        assert collection.location == 1

    def test_collection_properties_local(self):
        collection = CollectionCosmosDB(self.span, False, self.created_by)
        assert collection.collection_name == "test_collection_name"
        # For local, use collection name and user id to generate collection id
        assert collection.collection_id == "test_collection_name_test_user_id"
        assert collection.location == 0

        self.span.attributes = {"batch_run_id": "test_batch_run_id"}
        collection = CollectionCosmosDB(self.span, False, self.created_by)
        assert collection.collection_name == "test_collection_name"
        assert collection.collection_id == "test_batch_run_id"
        assert collection.location == 0

    def test_create_collection_if_not_exist(self):
        client = mock.Mock()
        with mock.patch("promptflow.azure._storage.cosmosdb.collection.safe_create_cosmosdb_item") as mock_safe_write:
            self.collection.create_collection_if_not_exist(client)
            mock_safe_write.assert_called_once()

    def test_update_collection_updated_at(self):
        client = mock.Mock()
        self.span.attributes = dict()
        self.span.resource = {"collection.id": "test_collection_id"}

        self.collection.update_collection_updated_at_info(client)

        client.patch_item.assert_called_once()

    def test_batch_run_operation(self):
        client = mock.Mock()
        self.span.attributes = {"batch_run_id": "test_batch_run_id"}
        self.span.resource = {"collection.id": "test_collection_id"}

        with mock.patch("promptflow.azure._storage.cosmosdb.summary.safe_create_cosmosdb_item") as mock_safe_write:
            self.collection.create_collection_if_not_exist(client)
            mock_safe_write.assert_not_called()

        self.collection.create_collection_if_not_exist(client)
        client.patch_item.assert_not_called()
