# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from sqlalchemy import TEXT, Column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import EXP_NODE_RUN_TABLE_NAME
from promptflow._sdk._errors import ExperimentNodeRunNotFoundError

from .retry import sqlite_retry
from .session import mgmt_db_session

Base = declarative_base()


class ExperimentNodeRun(Base):
    __tablename__ = EXP_NODE_RUN_TABLE_NAME

    snapshot_id = Column(TEXT, primary_key=True)
    run_id = Column(TEXT)
    node_name = Column(TEXT, nullable=False)
    experiment_name = Column(TEXT, nullable=False)
    status = Column(TEXT, nullable=False)

    # schema version, increase the version number when you change the schema
    __pf_schema_version__ = "1"

    @staticmethod
    @sqlite_retry
    def create_or_update(node_run: "ExperimentNodeRun") -> None:
        session = mgmt_db_session()
        snapshot_id = node_run.snapshot_id
        try:
            session.add(node_run)
            session.commit()
        except IntegrityError:
            session = mgmt_db_session()
            # Remove the _sa_instance_state
            update_dict = {k: v for k, v in node_run.__dict__.items() if not k.startswith("_")}
            session.query(ExperimentNodeRun).filter(ExperimentNodeRun.snapshot_id == snapshot_id).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def get_by_snapshot_id(snapshot_id: str, raise_error=True) -> "ExperimentNodeRun":
        with mgmt_db_session() as session:
            node_run = session.query(ExperimentNodeRun).filter(ExperimentNodeRun.snapshot_id == snapshot_id).first()
            if node_run is None and raise_error:
                raise ExperimentNodeRunNotFoundError(f"Not found the node run with snapshot id {snapshot_id!r}.")
            return node_run

    @staticmethod
    @sqlite_retry
    def delete(snapshot_id: str) -> None:
        with mgmt_db_session() as session:
            session.query(ExperimentNodeRun).filter(ExperimentNodeRun.snapshot_id == snapshot_id).delete()
            session.commit()
