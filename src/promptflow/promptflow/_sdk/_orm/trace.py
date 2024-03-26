# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import typing

from sqlalchemy import INTEGER, JSON, REAL, TEXT, TIMESTAMP, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from promptflow._sdk._constants import (
    EVENT_TABLENAME,
    EVENT_TRACE_ID_SPAN_ID_INDEX_NAME,
    LINE_RUN_PARENT_ID_INDEX_NAME,
    LINE_RUN_RUN_LINE_NUMBER_INDEX_NAME,
    LINE_RUN_TABLENAME,
    LINE_RUN_TRACE_ID_SPAN_ID_INDEX_NAME,
    SPAN_TABLENAME,
    SPAN_TRACE_ID_INDEX_NAME,
    SPAN_TRACE_ID_SPAN_ID_INDEX_NAME,
)
from promptflow._sdk._errors import LineRunNotFoundError

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

    __table_args__ = (Index(EVENT_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),)

    @staticmethod
    @sqlite_retry
    def get(event_id: str) -> "Event":
        with trace_mgmt_db_session() as session:
            event = session.query(Event).filter(Event.event_id == event_id).first()
            # TODO: validate event is None
            return event

    @staticmethod
    @sqlite_retry
    def list(trace_id: str, span_id: str) -> typing.List["Event"]:
        with trace_mgmt_db_session() as session:
            events = session.query(Event).filter(Event.trace_id == trace_id, Event.span_id == span_id).all()
            return events


class Span(Base):
    __tablename__ = SPAN_TABLENAME

    trace_id: Mapped[str] = mapped_column(TEXT)
    span_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    name: Mapped[str] = mapped_column(TEXT)
    context: Mapped[typing.Dict] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(TEXT)
    parent_id: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    start_time: Mapped[datetime.datetime] = mapped_column(TIMESTAMP)
    end_time: Mapped[datetime.datetime] = mapped_column(TIMESTAMP)
    status: Mapped[typing.Dict] = mapped_column(JSON)
    attributes: Mapped[typing.Optional[typing.Dict]] = mapped_column(JSON, nullable=True)
    links: Mapped[typing.Optional[typing.List]] = mapped_column(JSON, nullable=True)
    events: Mapped[typing.Optional[typing.List]] = mapped_column(JSON, nullable=True)
    resource: Mapped[typing.Dict] = mapped_column(JSON)

    __table_args__ = (
        Index(SPAN_TRACE_ID_INDEX_NAME, "trace_id"),
        Index(SPAN_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),
    )

    @staticmethod
    @sqlite_retry
    def get(span_id: str, trace_id: typing.Optional[str] = None) -> "Span":
        with trace_mgmt_db_session() as session:
            query = session.query(Span)
            if trace_id is not None:
                query = query.filter(Span.trace_id == trace_id, Span.span_id == span_id)
            else:
                query = query.filter(Span.span_id == span_id)
            span = query.first()
            # TODO: validate span is None
            return span

    @staticmethod
    @sqlite_retry
    def list(trace_id: str) -> typing.List["Span"]:
        with trace_mgmt_db_session() as session:
            spans = session.query(Span).filter(Span.trace_id == trace_id).all()
            return spans


class LineRun(Base):
    __tablename__ = LINE_RUN_TABLENAME

    line_run_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    trace_id: Mapped[str] = mapped_column(TEXT)
    root_span_id: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    inputs: Mapped[typing.Optional[typing.Dict]] = mapped_column(JSON, nullable=True)
    outputs: Mapped[typing.Optional[typing.Dict]] = mapped_column(JSON, nullable=True)
    start_time: Mapped[datetime.datetime] = mapped_column(TIMESTAMP)
    end_time: Mapped[typing.Optional[datetime.datetime]] = mapped_column(TIMESTAMP, nullable=True)
    status: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    duration: Mapped[typing.Optional[float]] = mapped_column(REAL, nullable=True)
    name: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    kind: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    cumulative_token_count: Mapped[typing.Optional[typing.Dict]] = mapped_column(JSON, nullable=True)
    parent_id: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    run: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    line_number: Mapped[typing.Optional[int]] = mapped_column(INTEGER, nullable=True)
    experiment: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    session_id: Mapped[typing.Optional[str]] = mapped_column(TEXT, nullable=True)
    collection: Mapped[str] = mapped_column(TEXT)

    __table_args__ = (
        Index(LINE_RUN_TRACE_ID_SPAN_ID_INDEX_NAME, "trace_id", "span_id"),
        Index(LINE_RUN_RUN_LINE_NUMBER_INDEX_NAME, "run", "line_number"),
        Index(LINE_RUN_PARENT_ID_INDEX_NAME, "parent_id"),
    )

    @staticmethod
    @sqlite_retry
    def get(line_run_id: str) -> "LineRun":
        with trace_mgmt_db_session() as session:
            line_run = session.query(LineRun).filter(LineRun.line_run_id == line_run_id).first()
            if line_run is None:
                raise LineRunNotFoundError(f"Line run {line_run_id!r} cannot found.")
            return line_run

    @staticmethod
    @sqlite_retry
    def _get_with_run_and_line_number(run: str, line_number: int) -> typing.Optional["LineRun"]:
        # this function is currently exclusively used to query parent line run
        with trace_mgmt_db_session() as session:
            line_run = (
                session.query(LineRun)
                .filter(
                    LineRun.run == run,
                    LineRun.line_number == line_number,
                )
                .first()
            )
            return line_run

    @sqlite_retry
    def _update(self) -> None:
        update_dict = {
            "root_span_id": self.root_span_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "end_time": self.end_time,
            "status": self.status,
            "duration": self.duration,
            "name": self.name,
            "kind": self.kind,
            "cumulative_token_count": self.cumulative_token_count,
        }
        with trace_mgmt_db_session() as session:
            session.query(LineRun).filter(LineRun.line_run_id == self.line_run_id).update(update_dict)
            session.commit()
