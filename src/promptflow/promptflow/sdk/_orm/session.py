# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import List, Union

from filelock import FileLock
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

from promptflow.sdk._constants import (
    CONNECTION_TABLE_NAME,
    LOCAL_MGMT_DB_PATH,
    LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH,
    RUN_INFO_TABLENAME,
)
from promptflow.sdk._utils import use_customized_encryption_key

session_maker = None
lock = FileLock(LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH)


def mgmt_db_session() -> Session:
    global session_maker
    global lock

    if session_maker is not None:
        return session_maker()

    lock.acquire()
    try:  # try-finally to always release lock
        if session_maker is not None:
            return session_maker()
        if not LOCAL_MGMT_DB_PATH.parent.is_dir():
            LOCAL_MGMT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{str(LOCAL_MGMT_DB_PATH)}")

        from promptflow.sdk._orm import Connection

        create_or_update_run_table(engine)
        create_table_if_not_exists(engine, CONNECTION_TABLE_NAME, Connection)
        session_maker = sessionmaker(bind=engine)
    finally:
        lock.release()

    return session_maker()


def compare_schema(schema1: dict, schema2: dict) -> bool:
    def _partially_compare(_schema1: dict, _schema2: dict) -> bool:
        for k in _schema1:
            if k not in _schema2:
                return False
            column1, column2 = _schema1[k], _schema2[k]
            # check type and nullable
            if column1["type"] != column2["type"] or column1["nullable"] != column2["nullable"]:
                return False
        return True

    # schema1 over schema2
    if not _partially_compare(schema1, schema2):
        return False
    # schema2 over schema1
    if not _partially_compare(schema2, schema1):
        return False
    return True


def build_copy_sql(old_name: str, new_name: str, old_columns: List[str], new_columns: List[str]) -> str:
    insert_stmt = f"INSERT INTO {new_name}"
    # append some NULLs for new columns
    columns = old_columns.copy() + ["NULL"] * (len(new_columns) - len(old_columns))
    select_stmt = "SELECT " + ", ".join(columns) + f" FROM {old_name}"
    sql = f"{insert_stmt} {select_stmt};"
    return sql


def create_or_update_run_table(engine) -> None:
    from promptflow.sdk._orm import RunInfo

    if not inspect(engine).has_table(RUN_INFO_TABLENAME):
        RunInfo.metadata.create_all(engine)
        return

    # compare existing and current schema
    # existing
    existing_columns = inspect(engine).get_columns(RUN_INFO_TABLENAME)
    existing_schema = {
        column["name"]: {"type": type(column["type"]).__name__.lower(), "nullable": column["nullable"]}
        for column in existing_columns
    }
    # current
    current_schema = {
        column.name: {"type": type(column.type).__name__.lower(), "nullable": column.nullable}
        for column in RunInfo.__table__.columns
    }
    # same schema, no action needed
    if compare_schema(existing_schema, current_schema):
        return
    # different schema, we need to:
    # 1. rename existing table name
    # 2. create table with current schema
    # 3. copy data from renamed table to new table
    # 4. drop renamed table
    renamed_table_name = f"{RUN_INFO_TABLENAME}_old"
    rename_sql = f"ALTER TABLE {RUN_INFO_TABLENAME} RENAME TO {renamed_table_name};"
    create_table_sql = str(CreateTable(RunInfo.__table__).compile(engine))
    copy_sql = build_copy_sql(
        old_name=renamed_table_name,
        new_name=RUN_INFO_TABLENAME,
        old_columns=[column["name"] for column in existing_columns],
        new_columns=[column.name for column in RunInfo.__table__.columns],
    )
    drop_sql = f"DROP TABLE {renamed_table_name};"
    # note that we should do above in one transaction
    with engine.begin() as connection:
        connection.execute(rename_sql)
        connection.execute(create_table_sql)
        connection.execute(copy_sql)
        connection.execute(drop_sql)
    return


def create_table_if_not_exists(engine, table_name, orm_class) -> None:
    if inspect(engine).has_table(table_name):
        return
    try:
        if inspect(engine).has_table(table_name):
            return
        orm_class.metadata.create_all(engine)
    except OperationalError as e:
        # only ignore error if table already exists
        expected_error_message = f"table {table_name} already exists"
        if expected_error_message not in str(e):
            raise


@contextmanager
def mgmt_db_rebase(mgmt_db_path: Union[Path, PathLike, str], customized_encryption_key: str = None) -> Session:
    """
    This function will change the constant LOCAL_MGMT_DB_PATH to the new path so very dangerous.
    It is created for pf flow export only and need to be removed in further version.
    """
    global session_maker
    global LOCAL_MGMT_DB_PATH

    origin_local_db_path = LOCAL_MGMT_DB_PATH

    LOCAL_MGMT_DB_PATH = mgmt_db_path
    session_maker = None

    if customized_encryption_key:
        with use_customized_encryption_key(customized_encryption_key):
            yield
    else:
        yield

    LOCAL_MGMT_DB_PATH = origin_local_db_path
    session_maker = None
