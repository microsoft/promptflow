# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
from enum import Enum
from typing import List, Optional, Union

from sqlalchemy import TEXT, Boolean, Column, Index
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import EXPERIMENT_CREATED_ON_INDEX_NAME, EXPERIMENT_TABLE_NAME, ListViewType
from promptflow._sdk._errors import ExperimentExistsError, ExperimentNotFoundError

from ...exceptions import ErrorTarget, UserErrorException
from .retry import sqlite_retry
from .session import mgmt_db_session

Base = declarative_base()


class Experiment(Base):
    __tablename__ = EXPERIMENT_TABLE_NAME

    name = Column(TEXT, primary_key=True)
    created_on = Column(TEXT, nullable=False)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    status = Column(TEXT, nullable=False)
    description = Column(TEXT)  # updated by users
    properties = Column(TEXT)
    archived = Column(Boolean, default=False)
    nodes = Column(TEXT)  # json(list of json) string
    node_runs = Column(TEXT)  # json(list of json) string
    # NOTE: please always add columns to the tail, so that we can easily handle schema changes;
    #       also don't forget to update `__pf_schema_version__` when you change the schema
    # NOTE: keep in mind that we need to well handle runs with legacy schema;
    #       normally new fields will be `None`, remember to handle them properly
    last_start_time = Column(TEXT)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    last_end_time = Column(TEXT)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    data = Column(TEXT)  # json string of data (list of dict)
    inputs = Column(TEXT)  # json string of inputs (list of dict)

    __table_args__ = (Index(EXPERIMENT_CREATED_ON_INDEX_NAME, "created_on"),)
    # schema version, increase the version number when you change the schema
    __pf_schema_version__ = "1"

    @sqlite_retry
    def dump(self) -> None:
        with mgmt_db_session() as session:
            try:
                session.add(self)
                session.commit()
            except IntegrityError as e:
                # catch "sqlite3.IntegrityError: UNIQUE constraint failed: run_info.name" to raise RunExistsError
                # otherwise raise the original error
                if "UNIQUE constraint failed" not in str(e):
                    raise
                raise ExperimentExistsError(f"Experiment name {self.name!r} already exists.")
            except Exception as e:
                raise UserErrorException(target=ErrorTarget.CONTROL_PLANE_SDK, message=str(e), error=e)

    @sqlite_retry
    def archive(self) -> None:
        if self.archived is True:
            return
        self.archived = True
        with mgmt_db_session() as session:
            session.query(Experiment).filter(Experiment.name == self.name).update({"archived": self.archived})
            session.commit()

    @sqlite_retry
    def restore(self) -> None:
        if self.archived is False:
            return
        self.archived = False
        with mgmt_db_session() as session:
            session.query(Experiment).filter(Experiment.name == self.name).update({"archived": self.archived})
            session.commit()

    @sqlite_retry
    def update(
        self,
        *,
        status: Optional[str] = None,
        description: Optional[str] = None,
        last_start_time: Optional[Union[str, datetime.datetime]] = None,
        last_end_time: Optional[Union[str, datetime.datetime]] = None,
        node_runs: Optional[str] = None,
        inputs: Optional[str] = None,
        data: Optional[str] = None,
    ) -> None:
        update_dict = {}
        if status is not None:
            self.status = status
            update_dict["status"] = self.status
        if description is not None:
            self.description = description
            update_dict["description"] = self.description
        if last_start_time is not None:
            self.last_start_time = last_start_time if isinstance(last_start_time, str) else last_start_time.isoformat()
            update_dict["last_start_time"] = self.last_start_time
        if last_end_time is not None:
            self.last_end_time = last_end_time if isinstance(last_end_time, str) else last_end_time.isoformat()
            update_dict["last_end_time"] = self.last_end_time
        if node_runs is not None:
            self.node_runs = node_runs
            update_dict["node_runs"] = self.node_runs
        if inputs is not None:
            self.inputs = inputs
            update_dict["inputs"] = self.inputs
        if data is not None:
            self.data = data
            update_dict["data"] = self.data
        with mgmt_db_session() as session:
            session.query(Experiment).filter(Experiment.name == self.name).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def get(name: str) -> "Experiment":
        with mgmt_db_session() as session:
            run_info = session.query(Experiment).filter(Experiment.name == name).first()
        if run_info is None:
            raise ExperimentNotFoundError(f"Experiment {name!r} cannot be found.")
        return run_info

    @staticmethod
    @sqlite_retry
    def list(max_results: Optional[int], list_view_type: ListViewType) -> List["Experiment"]:
        with mgmt_db_session() as session:
            basic_statement = session.query(Experiment)
            # filter by archived
            list_view_type = list_view_type.value if isinstance(list_view_type, Enum) else list_view_type
            if list_view_type == ListViewType.ACTIVE_ONLY.value:
                basic_statement = basic_statement.filter(Experiment.archived == False)  # noqa: E712
            elif list_view_type == ListViewType.ARCHIVED_ONLY.value:
                basic_statement = basic_statement.filter(Experiment.archived == True)  # noqa: E712
            basic_statement = basic_statement.order_by(Experiment.created_on.desc())

            if isinstance(max_results, int):
                return [result for result in basic_statement.limit(max_results)]
            else:
                return [result for result in basic_statement.all()]

    @staticmethod
    @sqlite_retry
    def delete(name: str) -> None:
        with mgmt_db_session() as session:
            result = session.query(Experiment).filter(Experiment.name == name).first()
            if result is not None:
                session.delete(result)
                session.commit()
            else:
                raise ExperimentNotFoundError(f"Experiment {name!r} cannot be found.")
