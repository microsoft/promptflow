# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from sqlalchemy import TEXT, Column, Index
from sqlalchemy.orm import declarative_base

from promptflow._sdk._constants import SPAN_TABLENAME

from .retry import sqlite_retry
from .session import otel_mgmt_db_session

Base = declarative_base()


class Span(Base):
    __tablename__ = SPAN_TABLENAME

    span_id = Column(TEXT, primary_key=True)
    trace_id = Column(TEXT)
    parent_id = Column(TEXT, nullable=True)
    # we might not need `experiment_name` if we have partition,
    # then the file name should be `experiment_name` or "default"
    experiment_name = Column(TEXT, nullable=True)
    run_name = Column(TEXT, nullable=True)
    path = Column(TEXT)
    content = Column(TEXT)  # JSON string

    __table_args__ = (
        Index("idx_span_experiment_name", "experiment_name"),
        Index("idx_span_run_name", "run_name"),
    )

    @sqlite_retry
    def persist(self) -> None:
        with otel_mgmt_db_session() as session:
            session.add(self)
            session.commit()
