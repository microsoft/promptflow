# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import os
from contextlib import contextmanager
from pathlib import Path
from typing import List, Union

from filelock import FileLock
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

from promptflow._sdk._constants import (
    CONNECTION_TABLE_NAME,
    EVENT_TABLENAME,
    EXP_NODE_RUN_TABLE_NAME,
    EXPERIMENT_CREATED_ON_INDEX_NAME,
    EXPERIMENT_TABLE_NAME,
    LINE_RUN_TABLENAME,
    LOCAL_MGMT_DB_PATH,
    LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH,
    ORCHESTRATOR_TABLE_NAME,
    RUN_INFO_CREATED_ON_INDEX_NAME,
    RUN_INFO_TABLENAME,
    SCHEMA_INFO_TABLENAME,
    SPAN_TABLENAME,
    TRACE_MGMT_DB_PATH,
    TRACE_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH,
)
from promptflow._sdk._utilities.general_utils import (
    get_promptflow_sdk_version,
    print_red_error,
    print_yellow_warning,
    use_customized_encryption_key,
)

# though we have removed the upper bound of SQLAlchemy version in setup.py
# still silence RemovedIn20Warning to avoid unexpected warning message printed to users
# for those who still use SQLAlchemy<2.0.0
os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"

session_maker = None
trace_session_maker = None
lock = FileLock(LOCAL_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH)
trace_lock = FileLock(TRACE_MGMT_DB_SESSION_ACQUIRE_LOCK_PATH)


def support_transaction(engine):
    # workaround to make SQLite support transaction; reference to SQLAlchemy doc:
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    @event.listens_for(engine, "connect")
    def do_connect(db_api_connection, connection_record):
        # disable pysqlite emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        db_api_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # emit our own BEGIN
        conn.exec_driver_sql("BEGIN")

    return engine


def update_current_schema(engine, orm_class, tablename: str) -> None:
    sql = f"REPLACE INTO {SCHEMA_INFO_TABLENAME} (tablename, version) VALUES (:tablename, :version);"
    with engine.begin() as connection:
        connection.execute(text(sql), {"tablename": tablename, "version": orm_class.__pf_schema_version__})
    return


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
        engine = create_engine(f"sqlite:///{str(LOCAL_MGMT_DB_PATH)}?check_same_thread=False", future=True)
        engine = support_transaction(engine)

        from promptflow._sdk._configuration import Configuration
        from promptflow._sdk._orm import Connection, Experiment, ExperimentNodeRun, Orchestrator, RunInfo

        create_or_update_table(engine, orm_class=RunInfo, tablename=RUN_INFO_TABLENAME)
        create_table_if_not_exists(engine, CONNECTION_TABLE_NAME, Connection)
        create_table_if_not_exists(engine, ORCHESTRATOR_TABLE_NAME, Orchestrator)
        create_table_if_not_exists(engine, EXP_NODE_RUN_TABLE_NAME, ExperimentNodeRun)

        create_index_if_not_exists(engine, RUN_INFO_CREATED_ON_INDEX_NAME, RUN_INFO_TABLENAME, "created_on")
        if Configuration.get_instance().is_internal_features_enabled():
            create_or_update_table(engine, orm_class=Experiment, tablename=EXPERIMENT_TABLE_NAME)
            create_index_if_not_exists(engine, EXPERIMENT_CREATED_ON_INDEX_NAME, EXPERIMENT_TABLE_NAME, "created_on")

        session_maker = sessionmaker(bind=engine)
    except Exception as e:  # pylint: disable=broad-except
        # if we cannot manage to create the connection to the management database
        # we can barely do nothing but raise the exception with printing the error message
        error_message = f"Failed to create management database: {str(e)}"
        print_red_error(error_message)
        raise
    finally:
        lock.release()

    return session_maker()


def build_copy_sql(old_name: str, new_name: str, old_columns: List[str], new_columns: List[str]) -> str:
    insert_stmt = f"INSERT INTO {new_name}"
    # append some NULLs for new columns
    columns = old_columns.copy() + ["NULL"] * (len(new_columns) - len(old_columns))
    select_stmt = "SELECT " + ", ".join(columns) + f" FROM {old_name}"
    sql = f"{insert_stmt} {select_stmt};"
    return sql


def generate_legacy_tablename(engine, tablename: str) -> str:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(f"SELECT version FROM {SCHEMA_INFO_TABLENAME} where tablename=(:tablename)"),
                {"tablename": tablename},
            ).first()
            current_schema_version = result[0]
    except (OperationalError, TypeError):
        # schema info table not exists(OperationalError) or no version for the table(TypeError)
        # legacy tablename fallbacks to "v0_{timestamp}" - use timestamp to avoid duplication
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        current_schema_version = f"0_{timestamp}"
    return f"{tablename}_v{current_schema_version}"


def get_db_schema_version(engine, tablename: str) -> int:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(f"SELECT version FROM {SCHEMA_INFO_TABLENAME} where tablename=(:tablename)"),
                {"tablename": tablename},
            ).first()
            return int(result[0])
    except (OperationalError, TypeError):
        # schema info table not exists(OperationalError) or no version for the table(TypeError)
        # version fallbacks to 0
        return 0


def create_or_update_table(engine, orm_class, tablename: str) -> None:
    # create schema_info table if not exists
    sql = f"CREATE TABLE IF NOT EXISTS {SCHEMA_INFO_TABLENAME} (tablename TEXT PRIMARY KEY, version TEXT NOT NULL);"
    with engine.begin() as connection:
        connection.execute(text(sql))

    # no table in database yet
    # create table via ORM class and update schema info
    if not inspect(engine).has_table(tablename):
        orm_class.metadata.create_all(engine)
        update_current_schema(engine, orm_class, tablename)
        return

    db_schema_version = get_db_schema_version(engine, tablename)
    sdk_schema_version = int(orm_class.__pf_schema_version__)

    # same schema, no action needed
    if db_schema_version == sdk_schema_version:
        return
    elif db_schema_version > sdk_schema_version:
        # schema in database is later than SDK schema
        # though different, we have design principal that later schema will always have no less columns
        # while new columns should be nullable or with default value
        # so that older schema can always use existing schema
        # we print warning message but not do other action
        warning_message = (
            f"We have noticed that you are using an older SDK version: {get_promptflow_sdk_version()!r}.\n"
            "While we will do our best to ensure compatibility, "
            "we highly recommend upgrading to the latest version of SDK for the best experience."
        )
        print_yellow_warning(warning_message)
        return
    else:
        # schema in database is older than SDK schema
        # so we have to create table with new schema
        # in this case, we need to:
        # 1. rename existing table name
        # 2. create table with current schema
        # 3. copy data from renamed table to new table
        legacy_tablename = generate_legacy_tablename(engine, tablename)
        rename_sql = f"ALTER TABLE {tablename} RENAME TO {legacy_tablename};"
        create_table_sql = str(CreateTable(orm_class.__table__).compile(engine))
        copy_sql = build_copy_sql(
            old_name=legacy_tablename,
            new_name=tablename,
            old_columns=[column["name"] for column in inspect(engine).get_columns(tablename)],
            new_columns=[column.name for column in orm_class.__table__.columns],
        )
        # note that we should do above in one transaction
        with engine.begin() as connection:
            connection.execute(text(rename_sql))
            connection.execute(text(create_table_sql))
            connection.execute(text(copy_sql))
        # update schema info finally
        update_current_schema(engine, orm_class, tablename)
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


def create_index_if_not_exists(engine, index_name, table_name, col_name) -> None:
    # created_on
    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} (f{col_name});"
    with engine.begin() as connection:
        connection.execute(text(sql))
    return


@contextmanager
def mgmt_db_rebase(mgmt_db_path: Union[Path, os.PathLike, str], customized_encryption_key: str = None) -> Session:
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


def trace_mgmt_db_session() -> Session:
    global trace_session_maker
    global trace_lock

    if trace_session_maker is not None:
        return trace_session_maker()

    trace_lock.acquire()
    try:
        if trace_session_maker is not None:
            return trace_session_maker()
        if not TRACE_MGMT_DB_PATH.parent.is_dir():
            TRACE_MGMT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{str(TRACE_MGMT_DB_PATH)}", future=True)
        engine = support_transaction(engine)

        if any(
            [
                not inspect(engine).has_table(EVENT_TABLENAME),
                not inspect(engine).has_table(SPAN_TABLENAME),
                not inspect(engine).has_table(LINE_RUN_TABLENAME),
            ]
        ):
            from .trace import Base

            Base.metadata.create_all(engine)

        trace_session_maker = sessionmaker(bind=engine)
    except Exception as e:  # pylint: disable=broad-except
        # if we cannot manage to create the connection to the OpenTelemetry management database
        # we can barely do nothing but raise the exception with printing the error message
        error_message = f"Failed to create OpenTelemetry management database: {str(e)}"
        print_red_error(error_message)
        raise
    finally:
        trace_lock.release()

    return trace_session_maker()
