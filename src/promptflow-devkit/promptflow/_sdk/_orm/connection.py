# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import List, Optional

from sqlalchemy import TEXT, Column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import CONNECTION_TABLE_NAME
from promptflow._sdk._orm.retry import sqlite_retry

from .._errors import ConnectionNotFoundError
from .session import mgmt_db_session

Base = declarative_base()


class Connection(Base):
    __tablename__ = CONNECTION_TABLE_NAME

    connectionName = Column(TEXT, primary_key=True)
    connectionType = Column(TEXT, nullable=False)
    configs = Column(TEXT, nullable=False)  # For custom connection, configs can be
    customConfigs = Column(TEXT, nullable=False)  # For strong type connection, custom configs is an empty dict
    createdDate = Column(TEXT, nullable=False)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    lastModifiedDate = Column(TEXT, nullable=False)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    expiryTime = Column(TEXT)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string

    @staticmethod
    @sqlite_retry
    def create_or_update(connection: "Connection") -> None:
        session = mgmt_db_session()
        name = connection.connectionName
        try:
            session.add(connection)
            session.commit()
        except IntegrityError:
            session = mgmt_db_session()
            # Remove the _sa_instance_state
            update_dict = {k: v for k, v in connection.__dict__.items() if not k.startswith("_")}
            update_dict.pop("createdDate")
            session.query(Connection).filter(Connection.connectionName == name).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def get(name: str, raise_error=True) -> "Connection":
        with mgmt_db_session() as session:
            connection = session.query(Connection).filter(Connection.connectionName == name).first()
            if connection is None and raise_error:
                raise ConnectionNotFoundError(f"Connection {name!r} is not found.")
            return connection

    @staticmethod
    @sqlite_retry
    def list(max_results: Optional[int] = None, all_results: bool = False) -> List["Connection"]:
        with mgmt_db_session() as session:
            if all_results:
                return [run_info for run_info in session.query(Connection).all()]
            else:
                return [run_info for run_info in session.query(Connection).limit(max_results)]

    @staticmethod
    @sqlite_retry
    def delete(name: str) -> None:
        with mgmt_db_session() as session:
            session.query(Connection).filter(Connection.connectionName == name).delete()
            session.commit()
