# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from sqlalchemy import TEXT, Column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import EXP_NODE_RUN_TABLE_NAME, ExperimentNodeRunStatus
from promptflow._sdk._errors import ExperimentNodeRunNotFoundError

from .retry import sqlite_retry
from .session import mgmt_db_session

Base = declarative_base()


class ExperimentNodeRun(Base):
    __tablename__ = EXP_NODE_RUN_TABLE_NAME

    run_id = Column(TEXT, primary_key=True)
    snapshot_id = Column(TEXT)
    node_name = Column(TEXT, nullable=False)
    experiment_name = Column(TEXT, nullable=False)
    status = Column(TEXT, nullable=False)

    # schema version, increase the version number when you change the schema
    __pf_schema_version__ = "1"

    @staticmethod
    @sqlite_retry
    def create_or_update(node_run: "ExperimentNodeRun") -> None:
        session = mgmt_db_session()
        run_id = node_run.run_id
        try:
            session.add(node_run)
            session.commit()
        except IntegrityError:
            session = mgmt_db_session()
            # Remove the _sa_instance_state
            update_dict = {k: v for k, v in node_run.__dict__.items() if not k.startswith("_")}
            session.query(ExperimentNodeRun).filter(ExperimentNodeRun.run_id == run_id).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def delete(snapshot_id: str) -> None:
        with mgmt_db_session() as session:
            session.query(ExperimentNodeRun).filter(ExperimentNodeRun.snapshot_id == snapshot_id).delete()
            session.commit()

    @staticmethod
    @sqlite_retry
    def get(run_id: str, raise_error=True) -> "ExperimentNodeRun":
        with mgmt_db_session() as session:
            orchestrator = session.query(ExperimentNodeRun).filter(ExperimentNodeRun.run_id == run_id).first()
            if orchestrator is None and raise_error:
                raise ExperimentNodeRunNotFoundError(f"Not found the node run {run_id!r}.")
            return orchestrator

    @staticmethod
    @sqlite_retry
    def get_completed_node_by_snapshot_id(
        snapshot_id: str, experiment_name: str, raise_error=True
    ) -> "ExperimentNodeRun":
        with mgmt_db_session() as session:
            node_run = (
                session.query(ExperimentNodeRun)
                .filter(
                    ExperimentNodeRun.snapshot_id == snapshot_id,
                    ExperimentNodeRun.experiment_name == experiment_name,
                    ExperimentNodeRun.status == ExperimentNodeRunStatus.COMPLETED,
                )
                .first()
            )
            if node_run is None and raise_error:
                raise ExperimentNodeRunNotFoundError(
                    f"Not found the completed node run with snapshot id {snapshot_id!r}."
                )
            return node_run

    @staticmethod
    @sqlite_retry
    def get_node_runs_by_experiment(experiment_name: str) -> "ExperimentNodeRun":
        with mgmt_db_session() as session:
            node_runs = (
                session.query(ExperimentNodeRun).filter(ExperimentNodeRun.experiment_name == experiment_name).all()
            )
            return node_runs

    @sqlite_retry
    def update_status(self, status: str) -> None:
        update_dict = {"status": status}
        with mgmt_db_session() as session:
            session.query(ExperimentNodeRun).filter(ExperimentNodeRun.run_id == self.run_id).update(update_dict)
            session.commit()
