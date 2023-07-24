from dataclasses import dataclass, field, asdict
from datetime import datetime

from promptflow.storage.sqlite_client import SqliteClient, INDEX, PRIMARY_KEY
from promptflow.contracts.run_info import RunInfo


@dataclass
class CacheRecord:
    run_id: str
    hash_id: str
    flow_run_id: str
    flow_id: str
    cache_string: str
    end_time: datetime


@dataclass
class LocalCacheRecord:
    """To store in local db."""
    run_id: str = field(metadata={PRIMARY_KEY: True})
    hash_id: str = field(metadata={INDEX: True})
    flow_run_id: str
    flow_id: str
    cache_string: str
    end_time: datetime


class AbstractCacheStorage:
    def get_cache_record_list(hash_id: str) -> CacheRecord:
        pass

    def persist_cache_result(run_info: RunInfo):
        pass


class LocalCacheStorage(AbstractCacheStorage):
    @classmethod
    def create_tables(cls, db_folder_path: str, db_name: str, test_mode: bool = False):
        """Create db tables if not exists. If table exists, check if columns are consistent with associated class.

        Note that this method involves disk io, it is not safe to be invoked concurrently.
        """
        # Create table for local cache record.
        SqliteClient.create_table_if_not_exists(
            db_folder_path,
            db_name,
            LocalCacheRecord,
            test_mode)

    def __init__(self, db_folder_path: str, db_name: str, test_mode: bool = False):
        """Create table clients and create db tables if not exists.

        This method should be invoked after create_tables.
        After invoking create_tables, this method is safe to be invoked concurrently; otherwise it is not.
        """
        self._sqlite_client = SqliteClient(
            db_folder_path,
            db_name,
            LocalCacheRecord,
            in_memory=test_mode)  # If test mode, create sqlite db in memory.

    def get_cache_record_list(self, hash_id: str) -> CacheRecord:
        local_cache_list = self._sqlite_client.get_by_field(hash_id=hash_id)
        return [CacheRecord(**asdict(c)) for c in local_cache_list]

    def persist_cache_result(self, run_info: RunInfo, hash_id: str, cache_string: str, flow_id: str):
        cache_record = LocalCacheRecord(
            run_id=run_info.run_id,
            hash_id=hash_id,
            flow_run_id=run_info.flow_run_id,
            flow_id=flow_id,
            cache_string=cache_string,
            end_time=run_info.end_time
        )
        self._sqlite_client.insert(cache_record)
