import datetime

import pytest

from promptflow.azure._storage.blob.client import _datastore_cache, _get_datastore_client_key, _get_datastore_from_cache
from promptflow.azure._utils._datastore_type import DatastoreType


@pytest.mark.unittest
class TestBlobClient:
    def test_datastore_type_compat(self):
        assert DatastoreType.AZURE_BLOB.value == "AzureBlob"
        assert DatastoreType.AZURE_DATA_LAKE_GEN2.value == "AzureDataLakeGen2"
        assert DatastoreType.AZURE_FILE.value == "AzureFile"

    def test_get_datastore_from_cache(self):
        _datastore_cache["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(0, -1),  # already expire
            "datastore_definition": "test",
            "datastore_credential": "test_credential",
        }
        datastore_definition, datastore_credential = _get_datastore_from_cache("test")
        assert datastore_definition is None
        assert datastore_credential is None

        _datastore_cache["test"] = {
            "expire_at": datetime.datetime.now() + datetime.timedelta(1, 0),  # expire after 1 day
            "datastore_definition": "test",
            "datastore_credential": "test_credential",
        }
        datastore_definition, datastore_credential = _get_datastore_from_cache("test")
        assert datastore_definition == "test"
        assert datastore_credential == "test_credential"

    def test_get_datastore_client_key(self):
        assert _get_datastore_client_key("sub", "rg", "ws") == "sub@rg@ws"
