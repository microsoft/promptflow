# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import typing

from sqlalchemy import TEXT, Column, Index, and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, declarative_base

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk._constants import SPAN_TABLENAME

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
    ) -> typing.List["Span"]:
        with trace_mgmt_db_session() as session:
            stmt: Query = session.query(Span)
            if session_id is not None:
                stmt = stmt.filter(Span.session_id == session_id)
            stmt = stmt.order_by(text("json_extract(span.content, '$.start_time') asc"))
            return [span for span in stmt.all()]


class LineRun:
    """Line run is an abstraction of spans, which is not persisted in the database."""

    @staticmethod
    def list(
        session_id: typing.Optional[str] = None,
        line_run_id: typing.Optional[str] = None,
    ) -> typing.List[typing.List[Span]]:
        with trace_mgmt_db_session() as session:
            if line_run_id is not None:
                stmt = LineRun._construct_query_with_line_run_id(session, line_run_id)
            else:
                stmt: Query = session.query(Span)
                if session_id is not None:
                    stmt = stmt.filter(Span.session_id == session_id)
                else:
                    # TODO: fully support query
                    raise NotImplementedError
            stmt = stmt.order_by(
                Span.trace_id,
                text("json_extract(span.content, '$.start_time') asc"),
            )
            line_runs = []
            current_spans: typing.List[Span] = []
            span: Span
            for span in stmt.all():
                if len(current_spans) == 0:
                    current_spans.append(span)
                    continue
                current_trace_id = current_spans[0].trace_id
                if span.trace_id == current_trace_id:
                    current_spans.append(span)
                    continue
                line_runs.append(copy.deepcopy(current_spans))
                current_spans = [span]
            if len(current_spans) > 0:
                line_runs.append(copy.deepcopy(current_spans))
            return line_runs

    @staticmethod
    def _construct_query_with_line_run_id(session: Session, line_run_id: str) -> Query:
        # TODO: maybe we need a LineRun table
        stmt: Query = session.query(Span).filter(and_(Span.trace_id == line_run_id, Span.parent_span_id is None))
        span: Span = stmt.first()
        attributes = json.loads(span.content).get(SpanFieldName.ATTRIBUTES, dict())
        stmt: Query = session.query(Span)
        # standard OpenTelemetry trace
        if (
            SpanAttributeFieldName.LINE_RUN_ID not in attributes
            and SpanAttributeFieldName.BATCH_RUN_ID not in attributes
        ):
            stmt = stmt.filter(Span.trace_id == line_run_id)
        # test scenario
        elif SpanAttributeFieldName.LINE_RUN_ID in attributes:
            expected_line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
            stmt = stmt.filter(
                or_(
                    text(
                        f"json_extract(json_extract(span.content, '$.attributes'), '$.line_run_id') = '{expected_line_run_id}'"  # noqa: E501
                    ),
                    text(
                        f"json_extract(json_extract(span.content, '$.attributes'), '$.\"referenced.line_run_id\"') = '{expected_line_run_id}'"  # noqa: E501
                    ),
                )
            )
        # batch run scenario
        else:
            expected_batch_run_id = attributes[SpanAttributeFieldName.BATCH_RUN_ID]
            stmt = stmt.filter(
                or_(
                    text(
                        f"json_extract(json_extract(span.content, '$.attributes'), '$.batch_run_id') = '{expected_batch_run_id}'"  # noqa: E501
                    ),
                    text(
                        f"json_extract(json_extract(span.content, '$.attributes'), '$.\"referenced.batch_run_id\"') = '{expected_batch_run_id}'"  # noqa: E501
                    ),
                )
            )
        return stmt
