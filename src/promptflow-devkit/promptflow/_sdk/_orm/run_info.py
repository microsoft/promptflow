# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
from enum import Enum
from typing import Dict, List, Optional, Union

from sqlalchemy import TEXT, Boolean, Column, Index
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import (
    RUN_INFO_CREATED_ON_INDEX_NAME,
    RUN_INFO_TABLENAME,
    FlowRunProperties,
    ListViewType,
)
from promptflow._sdk._errors import RunExistsError, RunNotFoundError

from .retry import sqlite_retry
from .session import mgmt_db_session

Base = declarative_base()


class RunInfo(Base):
    __tablename__ = RUN_INFO_TABLENAME

    name = Column(TEXT, primary_key=True)
    type = Column(TEXT)  # deprecated field
    created_on = Column(TEXT, nullable=False)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    status = Column(TEXT, nullable=False)
    display_name = Column(TEXT)  # can be edited by users
    description = Column(TEXT)  # updated by users
    tags = Column(TEXT)  # updated by users, json(list of json) string
    # properties: flow path, output path..., json string
    # as we can parse and get all information from parsing the YAML in memory,
    # we don't need to store any extra information in the database at all;
    # however, if there is any hot fields, we can store them here additionally.
    properties = Column(TEXT)
    archived = Column(Boolean, default=False)
    # NOTE: please always add columns to the tail, so that we can easily handle schema changes;
    #       also don't forget to update `__pf_schema_version__` when you change the schema
    # NOTE: keep in mind that we need to well handle runs with legacy schema;
    #       normally new fields will be `None`, remember to handle them properly
    start_time = Column(TEXT)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    end_time = Column(TEXT)  # ISO8601("YYYY-MM-DD HH:MM:SS.SSS"), string
    data = Column(TEXT)  # local path of original run data, string
    run_source = Column(TEXT)  # run source, string
    portal_url = Column(TEXT)  # portal url when trace destination is set to cloud, string

    __table_args__ = (Index(RUN_INFO_CREATED_ON_INDEX_NAME, "created_on"),)
    # schema version, increase the version number when you change the schema
    __pf_schema_version__ = "4"

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
                raise RunExistsError(f"Run name {self.name!r} already exists.")

    @sqlite_retry
    def archive(self) -> None:
        if self.archived is True:
            return
        self.archived = True
        with mgmt_db_session() as session:
            session.query(RunInfo).filter(RunInfo.name == self.name).update({"archived": self.archived})
            session.commit()

    @sqlite_retry
    def restore(self) -> None:
        if self.archived is False:
            return
        self.archived = False
        with mgmt_db_session() as session:
            session.query(RunInfo).filter(RunInfo.name == self.name).update({"archived": self.archived})
            session.commit()

    @sqlite_retry
    def update(
        self,
        *,
        status: Optional[str] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        start_time: Optional[Union[str, datetime.datetime]] = None,
        end_time: Optional[Union[str, datetime.datetime]] = None,
        system_metrics: Optional[Dict[str, int]] = None,
        portal_url: Optional[str] = None,
    ) -> None:
        update_dict = {}
        if status is not None:
            self.status = status
            update_dict["status"] = self.status
        if display_name is not None:
            self.display_name = display_name
            update_dict["display_name"] = self.display_name
        if description is not None:
            self.description = description
            update_dict["description"] = self.description
        if tags is not None:
            self.tags = json.dumps(tags)
            update_dict["tags"] = self.tags
        if start_time is not None:
            self.start_time = start_time if isinstance(start_time, str) else start_time.isoformat()
            update_dict["start_time"] = self.start_time
        if end_time is not None:
            self.end_time = end_time if isinstance(end_time, str) else end_time.isoformat()
            update_dict["end_time"] = self.end_time
        if portal_url is not None:
            self.portal_url = portal_url
            update_dict["portal_url"] = self.portal_url
        with mgmt_db_session() as session:
            # if not update system metrics, we can directly update the row;
            # otherwise, we need to get properties first, update the dict and finally update the row
            if system_metrics is None:
                session.query(RunInfo).filter(RunInfo.name == self.name).update(update_dict)
            else:
                # with high concurrency on same row, we may lose the earlier commit
                # we regard it acceptable as it should be an edge case to update properties
                # on same row with high concurrency;
                # if it's a concern, we can move those properties to an extra column
                run_info = session.query(RunInfo).filter(RunInfo.name == self.name).first()
                props = json.loads(run_info.properties)
                props[FlowRunProperties.SYSTEM_METRICS] = system_metrics.copy()
                update_dict["properties"] = json.dumps(props)
                session.query(RunInfo).filter(RunInfo.name == self.name).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def get(name: str) -> "RunInfo":
        with mgmt_db_session() as session:
            run_info = session.query(RunInfo).filter(RunInfo.name == name).first()
        if run_info is None:
            raise RunNotFoundError(f"Run name {name!r} cannot be found.")
        return run_info

    @staticmethod
    @sqlite_retry
    def search(search_name: str, max_results: Optional[int]):
        with mgmt_db_session() as session:
            statement = session.query(RunInfo).filter(RunInfo.name.like(f"{search_name}%"))

            if isinstance(max_results, int):
                return [run_info for run_info in statement.limit(max_results)]
            else:
                return [run_info for run_info in statement.all()]

    @staticmethod
    @sqlite_retry
    def list(max_results: Optional[int], list_view_type: ListViewType) -> List["RunInfo"]:
        with mgmt_db_session() as session:
            basic_statement = session.query(RunInfo)
            # filter by archived
            list_view_type = list_view_type.value if isinstance(list_view_type, Enum) else list_view_type
            if list_view_type == ListViewType.ACTIVE_ONLY.value:
                basic_statement = basic_statement.filter(RunInfo.archived == False)  # noqa: E712
            elif list_view_type == ListViewType.ARCHIVED_ONLY.value:
                basic_statement = basic_statement.filter(RunInfo.archived == True)  # noqa: E712
            basic_statement = basic_statement.order_by(RunInfo.created_on.desc())

            if isinstance(max_results, int):
                return [run_info for run_info in basic_statement.limit(max_results)]
            else:
                return [run_info for run_info in basic_statement.all()]

    @staticmethod
    @sqlite_retry
    def delete(name: str) -> None:
        with mgmt_db_session() as session:
            run_info = session.query(RunInfo).filter(RunInfo.name == name).first()
            if run_info is not None:
                session.delete(run_info)
                session.commit()
            else:
                raise RunNotFoundError(f"Run name {name!r} cannot be found.")
