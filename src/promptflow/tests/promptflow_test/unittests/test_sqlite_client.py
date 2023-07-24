import pytest
from datetime import datetime
from pathlib import Path
from dataclasses import field, dataclass

from promptflow.storage.sqlite_client import \
    SqliteClient, DuplicatedPrimaryKeyException, NotFoundException, PRIMARY_KEY, INDEX


DB_FOLDER_PATH = Path(__file__).parent / ".sqlitedb"
DB_NAME = "test.db"


@dataclass
class Entity:
    primary_key: str = field(metadata={PRIMARY_KEY: True})  # FlowRunId:ChildFlowRunId
    index_1: str = field(metadata={INDEX: True})
    index_2: str = field(metadata={INDEX: True})
    str_column: str
    datetime_column: datetime
    int_column: int
    float_column: float
    bool_column: bool


def _generate_entity():
    return Entity(
        primary_key="primary-key",
        index_1="index-1",
        index_2="index-2",
        str_column="str",
        datetime_column=datetime.now(),
        int_column=1,
        float_column=3.14,
        bool_column=True,
    )


@pytest.mark.unittest
def test_from_class():
    sqlite_client = SqliteClient(DB_FOLDER_PATH, DB_NAME, Entity, in_memory=True)
    assert sqlite_client._table.name == "Entity"
    assert sqlite_client._primary_key_column == "primary_key"
    assert len(sqlite_client._table.columns) == 8
    assert sqlite_client._table.has_index(["index_1"])
    assert sqlite_client._table.has_index(["index_2"])


@pytest.mark.unittest
def test_insert():
    sqlite_client = SqliteClient(DB_FOLDER_PATH, DB_NAME, Entity, in_memory=True)
    record = _generate_entity()
    sqlite_client.insert(record)
    return sqlite_client, record


@pytest.mark.unittest
def test_get():
    sqlite_client, record = test_insert()
    record_retrieved = sqlite_client.get(record.primary_key)
    assert record_retrieved == record


@pytest.mark.unittest
def test_get_by_field():
    sqlite_client, record = test_insert()
    record_retrieved = sqlite_client.get_by_field(index_1="index-1")
    assert len(record_retrieved) == 1
    assert record_retrieved[0] == record


@pytest.mark.unittest
def test_upsert():
    sqlite_client, record = test_insert()
    record.str_column = "new-str"
    sqlite_client.upsert(record)
    record_retrieved = sqlite_client.get_by_field(index_1="index-1")
    assert len(record_retrieved) == 1
    assert record_retrieved[0] == record


@pytest.mark.unittest
def test_insert_duplicate_exception():
    sqlite_client, record = test_insert()
    with pytest.raises(DuplicatedPrimaryKeyException):
        sqlite_client.insert(record)


@pytest.mark.unittest
def test_get_not_found_exception():
    sqlite_client, _ = test_insert()
    with pytest.raises(NotFoundException):
        sqlite_client.get("Not-existed primary key")


@pytest.mark.unittest
def test_query_not_found():
    sqlite_client, _ = test_insert()
    result = sqlite_client.get_by_field(index_1="Not-existed index")
    assert len(result) == 0


@pytest.mark.unittest
def test_dt():
    class DummyClass:
        pass

    with pytest.raises(ValueError):
        SqliteClient(DB_FOLDER_PATH, DB_NAME, DummyClass, in_memory=True)
