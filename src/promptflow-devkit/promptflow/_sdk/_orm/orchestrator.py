# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from sqlalchemy import INTEGER, TEXT, Column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import ORCHESTRATOR_TABLE_NAME
from promptflow._sdk._errors import ExperimentNotFoundError

from .retry import sqlite_retry
from .session import mgmt_db_session

Base = declarative_base()


class Orchestrator(Base):
    __tablename__ = ORCHESTRATOR_TABLE_NAME

    experiment_name = Column(TEXT, primary_key=True)
    pid = Column(INTEGER, nullable=True)
    status = Column(TEXT, nullable=False)
    # schema version, increase the version number when you change the schema
    __pf_schema_version__ = "1"

    @staticmethod
    @sqlite_retry
    def create_or_update(orchestrator: "Orchestrator") -> None:
        session = mgmt_db_session()
        experiment_name = orchestrator.experiment_name
        try:
            session.add(orchestrator)
            session.commit()
        except IntegrityError:
            session = mgmt_db_session()
            # Remove the _sa_instance_state
            update_dict = {k: v for k, v in orchestrator.__dict__.items() if not k.startswith("_")}
            session.query(Orchestrator).filter(Orchestrator.experiment_name == experiment_name).update(update_dict)
            session.commit()

    @staticmethod
    @sqlite_retry
    def get(experiment_name: str, raise_error=True) -> "Orchestrator":
        with mgmt_db_session() as session:
            orchestrator = session.query(Orchestrator).filter(Orchestrator.experiment_name == experiment_name).first()
            if orchestrator is None and raise_error:
                raise ExperimentNotFoundError(f"The experiment {experiment_name!r} hasn't been started yet.")
            return orchestrator

    @staticmethod
    @sqlite_retry
    def delete(name: str) -> None:
        with mgmt_db_session() as session:
            session.query(Orchestrator).filter(Orchestrator.experiment_name == name).delete()
            session.commit()
