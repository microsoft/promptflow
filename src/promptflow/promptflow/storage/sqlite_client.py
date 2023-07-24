import dataset
import os
from datetime import datetime
from dataset.types import Types
from sqlalchemy.exc import IntegrityError
from typing import List
import dataclasses
from dataclasses import fields, asdict
from sqlite3 import OperationalError

from promptflow.utils.retry_utils import retry


PRIMARY_KEY = "PrimaryKey"
INDEX = "INDEX"


def _get_type(t: type):
    if issubclass(t, str):
        return Types.string
    elif issubclass(t, int):
        return Types.integer
    elif issubclass(t, datetime):
        return Types.datetime
    elif issubclass(t, bool):
        return Types.boolean
    elif issubclass(t, float):
        return Types.float
    else:
        raise ValueError(f"No mapping defined from type {t} to sqlite db type.")


class DuplicatedPrimaryKeyException(Exception):
    pass


class NotFoundException(Exception):
    pass


class TableInfo:
    def __init__(self, db: dataset.Database, table: dataset.Table, primary_key: str):
        self.db = db
        self.table = table
        self.primary_key = primary_key


class SqliteClient:
    @classmethod
    def create_table_if_not_exists(
        cls,
        db_folder_path: str,
        db_name: str,
        class_: type,
        in_memory: bool = False,
        timeout_seconds: int = 30
    ) -> TableInfo:
        """Create db table if not exists. If table exists, check if columns are consistent with input class_.

        Note that this method involves disk io, it is not safe to be invoked concurrently.
        """
        # Check class_ is decorated by dataclass.
        if not dataclasses.is_dataclass(class_):
            raise ValueError(
                "Input class type must be decorated with dataclasses.dataclass."
            )

        table_name = class_.__name__  # table name is class name.

        col_name_to_field_meta = {
            field.name: field.metadata for field in fields(class_)
        }
        col_name_to_type = {field.name: field.type for field in fields(class_)}

        # Get primary key.
        primary_key_columns = [
            k for k, v in col_name_to_field_meta.items() if v.get(PRIMARY_KEY)
        ]
        if len(primary_key_columns) != 1:
            raise ValueError(
                f"One and only one primary key column is allowed! Got {len(primary_key_columns)}"
            )
        primary_key = primary_key_columns[0]

        # Get index column names.
        index_columns = [k for k, v in col_name_to_field_meta.items() if v.get(INDEX)]

        if not in_memory and not os.path.exists(db_folder_path):
            os.mkdir(db_folder_path)

        db_path = ":memory:" if in_memory else f"{db_folder_path}/{db_name}"
        # Set check_same_thread=False because different threads might use the same db.
        db = dataset.connect(f"sqlite:///{db_path}?check_same_thread=False",
                             on_connect_statements=[f'PRAGMA busy_timeout = {timeout_seconds*1000}'])

        # Create or load existing table.
        if table_name in db.tables:
            table = db.load_table(table_name)
        else:
            primary_col_type = _get_type(col_name_to_type.get(primary_key))
            table = db.create_table(
                table_name=table_name,
                primary_id=primary_key,
                primary_type=primary_col_type,
            )

        # Create columns
        for col_name, t in col_name_to_type.items():
            if not table.has_column(col_name):
                table.create_column(col_name, _get_type(t))

        # Create index for each index column.
        for index_col in index_columns:
            if not table.has_index([index_col]):
                table.create_index([index_col])

        return TableInfo(db, table, primary_key)

    def __init__(
        self,
        db_folder_path: str,
        db_name: str,
        class_: type,
        in_memory: bool = False,
        timeout_seconds: int = 30,
    ):
        """Create db table if not exists. If table exists, check if columns are consistent with input class_.

        This method should be invoked after create_table_if_not_exists.
        After invoking create_table_if_not_exists, this method is safe to be invoked concurrently; otherwise it is not.
        """
        table_info: TableInfo = self.create_table_if_not_exists(
            db_folder_path,
            db_name,
            class_,
            in_memory,
            timeout_seconds)
        self._class = class_
        self._db_folder_path = db_folder_path
        self._primary_key_column = table_info.primary_key
        self._db = table_info.db
        self._table = table_info.table

    @property
    def table(self):
        return self._table

    @retry(OperationalError, tries=3, delay=0.5, backoff=1)
    def get(self, primary_key: str) -> object:
        """Query by primary key. Raise NotFoundException if not existed."""
        with self._db:
            d = self._table.find_one(**{self._primary_key_column: primary_key})
        if d is None:
            raise NotFoundException(f"Entity with primary key {primary_key} not found.")
        return self._class(**d)

    @retry(OperationalError, tries=3, delay=0.5, backoff=1)
    def get_by_field(self, **kwargs) -> List[object]:
        """Query by column name. Return empty list if not found any.
        For example: table.get_by_field(hash_id='hash-id-value')
        """
        with self._db:
            return [self._class(**r) for r in self._table.find(**kwargs)]

    @retry(OperationalError, tries=3, delay=0.5, backoff=1)
    def insert(self, entity: object):
        """Insert entity."""
        d = asdict(entity)
        try:
            with self._db:
                self._table.insert(d)
        except IntegrityError as ex:
            raise DuplicatedPrimaryKeyException(
                f"Primary key {d.get(self._primary_key_column)} already exists."
            ) from ex

    @retry(OperationalError, tries=3, delay=0.5, backoff=1)
    def upsert(self, entity: object):
        """Upsert entity."""
        with self._db:
            self._table.upsert(asdict(entity), keys=[self._primary_key_column])

    def _add_index_column(self, col_name: str):
        if not self._table.has_index([col_name]):
            self._table.create_index([col_name])
