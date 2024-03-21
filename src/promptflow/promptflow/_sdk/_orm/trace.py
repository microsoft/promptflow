# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import typing

from sqlalchemy import TEXT, Column, Index, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, declarative_base

from promptflow._sdk._constants import SPAN_TABLENAME, TRACE_LIST_DEFAULT_LIMIT

from .retry import sqlite_retry
from .session import trace_mgmt_db_session

Base = declarative_base()


class Span(Base):
    __tablename__ = SPAN_TABLENAME

    name = Column(TEXT, nullable=False)
    trace_id = Column(TEXT, nullable=False)
    span_id = Column(TEXT, primary_key=True)
    parent_span_id = Column(TEXT, nullable=True)
    span_type = Column(TEXT, nullable=False)  # Function/Tool/Flow/LLM/LangChain...
    session_id = Column(TEXT, nullable=False)
    content = Column(TEXT)  # JSON string
    # prompt flow concepts
    path = Column(TEXT, nullable=True)
    run = Column(TEXT, nullable=True)
    experiment = Column(TEXT, nullable=True)

    __table_args__ = (
        Index("idx_span_name", "name"),
        Index("idx_span_span_type", "span_type"),
        Index("idx_span_session_id", "session_id"),
        Index("idx_span_run", "run"),
        Index("idx_span_experiment", "experiment"),
    )

    @sqlite_retry
    def persist(self) -> None:
        with trace_mgmt_db_session() as session:
            try:
                session.add(self)
                session.commit()
            except IntegrityError as e:
                # ignore "sqlite3.IntegrityError: UNIQUE constraint failed"
                # according to OTLP 1.1.0: https://opentelemetry.io/docs/specs/otlp/#duplicate-data
                # there might be duplicate data, we silently ignore it here
                if "UNIQUE constraint failed" not in str(e):
                    raise

    @staticmethod
    @sqlite_retry
    def list(
        session_id: typing.Optional[str] = None,
        trace_ids: typing.Optional[typing.List[str]] = None,
    ) -> typing.List["Span"]:
        with trace_mgmt_db_session() as session:
            stmt: Query = session.query(Span)
            if session_id is not None:
                stmt = stmt.filter(Span.session_id == session_id)
            if trace_ids is not None:
                stmt = stmt.filter(Span.trace_id.in_(trace_ids))
            stmt = stmt.order_by(text("json_extract(span.content, '$.start_time') asc"))
            if session_id is None and trace_ids is None:
                stmt = stmt.limit(TRACE_LIST_DEFAULT_LIMIT)
            return [span for span in stmt.all()]


class LineRun:
    """Line run is an abstraction of spans, which is not persisted in the database."""

    @staticmethod
    def _group_by_trace_id(stmt: Query) -> typing.List[Span]:
        res = list()
        current_spans = list()
        span: Span
        for span in stmt.all():
            if len(current_spans) == 0:
                current_spans.append(span)
                continue
            current_trace_id = current_spans[0].trace_id
            if span.trace_id == current_trace_id:
                current_spans.append(span)
                continue
            res.append(copy.deepcopy(current_spans))
            current_spans = [span]
        if len(current_spans) > 0:
            res.append(copy.deepcopy(current_spans))
        return res

    @staticmethod
    @sqlite_retry
    def list(
        session_id: typing.Optional[str] = None,
        experiments: typing.Optional[typing.List[str]] = None,
    ) -> typing.List[typing.List[Span]]:
        with trace_mgmt_db_session() as session:
            stmt: Query = session.query(Span)
            if session_id is not None:
                stmt = stmt.filter(Span.session_id == session_id)
            if experiments is not None:
                stmt = stmt.filter(Span.experiment.in_(experiments))
            stmt = stmt.order_by(
                Span.trace_id,
                text("json_extract(span.content, '$.start_time') asc"),
            )
            if session_id is None and experiments is None:
                stmt = stmt.limit(TRACE_LIST_DEFAULT_LIMIT)
            return LineRun._group_by_trace_id(stmt)

    @staticmethod
    @sqlite_retry
    def list_with_runs(runs: typing.List[str]) -> typing.List[Span]:
        with trace_mgmt_db_session() as session:
            stmt: Query = session.query(Span)
            runs_string = ""
            for run in runs:
                runs_string += f"'{run}',"
            runs_string = runs_string[:-1]  # remove the last comma
            stmt = stmt.filter(
                text(
                    f"(json_extract(json_extract(span.content, '$.attributes'), '$.batch_run_id') in ({runs_string}) OR "  # noqa: E501
                    f"json_extract(json_extract(span.content, '$.attributes'), '$.\"referenced.batch_run_id\"') in ({runs_string}))"  # noqa: E501
                )
            )
            stmt = stmt.order_by(
                Span.trace_id,
                text("json_extract(span.content, '$.start_time') asc"),
            )
            return LineRun._group_by_trace_id(stmt)

    @staticmethod
    @sqlite_retry
    def get_line_run(line_run_id: str) -> typing.List[Span]:
        with trace_mgmt_db_session() as session:
            sql = f"""
with trace as
(
    select
        json_extract(json_extract(span.content, '$.attributes'), '$.line_run_id') as line_run_id,
        json_extract(json_extract(span.content, '$.attributes'), '$.batch_run_id') as batch_run_id,
        json_extract(json_extract(span.content, '$.attributes'), '$.line_number') as line_number
    from span
    where trace_id = '{line_run_id}'
    limit 1
)
select name, trace_id, span_id, parent_span_id, span_type, session_id, content, path, run, experiment
from span s
join trace t
where
    json_extract(json_extract(s.content, '$.attributes'), '$.line_run_id') = t.line_run_id
    or json_extract(json_extract(s.content, '$.attributes'), '$.\"referenced.line_run_id\"') = t.line_run_id
    or (
        json_extract(json_extract(s.content, '$.attributes'), '$.batch_run_id') = t.batch_run_id
        and json_extract(json_extract(s.content, '$.attributes'), '$.line_number') = t.line_number
    )
    or (
        json_extract(json_extract(s.content, '$.attributes'), '$.\"referenced.batch_run_id\"') = t.batch_run_id
        and json_extract(json_extract(s.content, '$.attributes'), '$.line_number') = t.line_number
    )
"""
            rows = session.execute(text(sql))
            spans = []
            for row in rows:
                name, trace_id, span_id, parent_span_id, span_type, session_id, content, path, run, experiment = row
                span = Span(
                    name=name,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    span_type=span_type,
                    session_id=session_id,
                    content=content,
                    path=path,
                    run=run,
                    experiment=experiment,
                )
                spans.append(span)
            return spans
