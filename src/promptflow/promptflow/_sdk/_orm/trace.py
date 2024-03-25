# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from sqlalchemy import JSON, REAL, TEXT, TIMESTAMP, ForeignKeyConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from promptflow._sdk._constants import (
    EVENT_TABLENAME,
    EVENT_TRACE_ID_SPAN_ID_INDEX_NAME,
    LINE_RUN_TABLENAME,
    LINE_RUN_TRACE_ID_SPAN_ID_INDEX_NAME,
    SPAN_TABLENAME,
    SPAN_TRACE_ID_SPAN_ID_INDEX_NAME,
)

from .retry import sqlite_retry
from .session import trace_mgmt_db_session


class Base(DeclarativeBase):
    @sqlite_retry
    def persist(self) -> None:
        with trace_mgmt_db_session() as session:
            session.add(self)
            session.commit()


class Event(Base):
    __tablename__ = EVENT_TABLENAME

    event_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    trace_id: Mapped[str] = mapped_column(TEXT)
    span_id: Mapped[str] = mapped_column(TEXT)
    data: Mapped[str] = mapped_column(TEXT)

    span: Mapped["Span"] = relationship(back_populates="events")

    __table_args__ = (
        ForeignKeyConstraint([trace_id, span_id], [f"{SPAN_TABLENAME}.trace_id", f"{SPAN_TABLENAME}.span_id"]),
        Index(EVENT_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),
    )


class Span(Base):
    __tablename__ = SPAN_TABLENAME

    trace_id: Mapped[str] = mapped_column(TEXT)
    span_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    name: Mapped[str] = mapped_column(TEXT)
    context: Mapped[typing.Dict] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(TEXT)
    parent_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    start_time: Mapped[int] = mapped_column(TIMESTAMP)
    end_time: Mapped[int] = mapped_column(TIMESTAMP)
    status: Mapped[typing.Dict] = mapped_column(JSON)
    attributes: Mapped[typing.Dict | None] = mapped_column(JSON, nullable=True)
    links: Mapped[typing.Dict | None] = mapped_column(JSON, nullable=True)
    events: Mapped[typing.Dict | None] = mapped_column(JSON, nullable=True)
    resource: Mapped[typing.Dict] = mapped_column(JSON)

    events: Mapped[typing.List["Event"]] = relationship(back_populates="span")
    line_run: Mapped["LineRun"] = relationship(back_populates="span")

    __table_args__ = (Index(SPAN_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),)


class LineRun(Base):
    __tablename__ = LINE_RUN_TABLENAME

    line_run_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    trace_id: Mapped[str] = mapped_column(TEXT)
    span_id: Mapped[str] = mapped_column(TEXT)
    inputs: Mapped[typing.Dict] = mapped_column(JSON)
    outputs: Mapped[typing.Dict] = mapped_column(JSON)
    start_time: Mapped[int] = mapped_column(TIMESTAMP)
    end_time: Mapped[int] = mapped_column(TIMESTAMP)
    status: Mapped[str] = mapped_column(TEXT)
    latency: Mapped[float] = mapped_column(REAL)
    name: Mapped[str] = mapped_column(TEXT)
    kind: Mapped[str] = mapped_column(TEXT)
    cumulative_token_count: Mapped[typing.Dict | None] = mapped_column(JSON, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    run: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    experiment: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    session_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    collection: Mapped[str] = mapped_column(TEXT)

    span: Mapped["Span"] = relationship(back_populates="line_run")

    __table_args__ = (
        ForeignKeyConstraint([trace_id, span_id], [f"{SPAN_TABLENAME}.trace_id", f"{SPAN_TABLENAME}.span_id"]),
        Index(LINE_RUN_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),
    )
