# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import ast
import datetime
import typing
from dataclasses import dataclass

import sqlalchemy
from dateutil.parser import parse
from sqlalchemy import INTEGER, JSON, REAL, TEXT, TIMESTAMP, Column, Index
from sqlalchemy.orm import Mapped, Query, Session, declarative_base

from promptflow._sdk._constants import EVENT_TABLENAME, LINE_RUN_TABLENAME, SPAN_TABLENAME, TRACE_LIST_DEFAULT_LIMIT
from promptflow._sdk._errors import LineRunNotFoundError, WrongTraceSearchExpressionError

from .retry import sqlite_retry
from .session import trace_mgmt_db_session


class EventIndexName:
    TRACE_ID_SPAN_ID = "idx_events_trace_id_span_id"


class SpanIndexName:
    TRACE_ID = "idx_spans_trace_id"
    TRACE_ID_SPAN_ID = "idx_spans_trace_id_span_id"


class LineRunIndexName:
    RUN_LINE_NUMBER = "idx_line_runs_run_line_number"  # query parent line run
    PARENT_ID = "idx_line_runs_parent_id"
    COLLECTION = "idx_line_runs_collection"
    RUN = "idx_line_runs_run"
    EXPERIMENT = "idx_line_runs_experiment"
    TRACE_ID = "idx_line_runs_trace_id"
    SESSION_ID = "idx_line_runs_session_id"


Base = declarative_base()


class Event(Base):
    __tablename__ = EVENT_TABLENAME

    event_id: Mapped[str] = Column(TEXT, primary_key=True)
    trace_id: Mapped[str] = Column(TEXT)
    span_id: Mapped[str] = Column(TEXT)
    data: Mapped[str] = Column(TEXT)

    __table_args__ = (Index(EventIndexName.TRACE_ID_SPAN_ID, "trace_id", "span_id"),)

    @sqlite_retry
    def persist(self) -> None:
        with trace_mgmt_db_session() as session:
            session.add(self)
            session.commit()

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

    trace_id: Mapped[str] = Column(TEXT)
    span_id: Mapped[str] = Column(TEXT, primary_key=True)
    name: Mapped[str] = Column(TEXT)
    context: Mapped[typing.Dict] = Column(JSON)
    kind: Mapped[str] = Column(TEXT)
    parent_id: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    start_time: Mapped[datetime.datetime] = Column(TIMESTAMP)
    end_time: Mapped[datetime.datetime] = Column(TIMESTAMP)
    status: Mapped[typing.Dict] = Column(JSON)
    attributes: Mapped[typing.Optional[typing.Dict]] = Column(JSON, nullable=True)
    links: Mapped[typing.Optional[typing.List]] = Column(JSON, nullable=True)
    events: Mapped[typing.Optional[typing.List]] = Column(JSON, nullable=True)
    resource: Mapped[typing.Dict] = Column(JSON)

    __table_args__ = (
        Index(SpanIndexName.TRACE_ID, "trace_id"),
        Index(SpanIndexName.TRACE_ID_SPAN_ID, "trace_id", "span_id"),
    )

    @sqlite_retry
    def persist(self) -> None:
        with trace_mgmt_db_session() as session:
            session.merge(self)
            session.commit()

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
    def list(trace_ids: typing.Union[str, typing.List[str]]) -> typing.List["Span"]:
        if isinstance(trace_ids, str):
            trace_ids = [trace_ids]
        with trace_mgmt_db_session() as session:
            spans = session.query(Span).filter(Span.trace_id.in_(trace_ids)).all()
            return spans


class LineRun(Base):
    __tablename__ = LINE_RUN_TABLENAME

    line_run_id: Mapped[str] = Column(TEXT, primary_key=True)
    trace_id: Mapped[str] = Column(TEXT)
    root_span_id: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    inputs: Mapped[typing.Optional[typing.Dict]] = Column(JSON, nullable=True)
    outputs: Mapped[typing.Optional[typing.Dict]] = Column(JSON, nullable=True)
    start_time: Mapped[datetime.datetime] = Column(TIMESTAMP)
    end_time: Mapped[typing.Optional[datetime.datetime]] = Column(TIMESTAMP, nullable=True)
    status: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    duration: Mapped[typing.Optional[float]] = Column(REAL, nullable=True)
    name: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    kind: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    cumulative_token_count: Mapped[typing.Optional[typing.Dict]] = Column(JSON, nullable=True)
    parent_id: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    run: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    line_number: Mapped[typing.Optional[int]] = Column(INTEGER, nullable=True)
    experiment: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    session_id: Mapped[typing.Optional[str]] = Column(TEXT, nullable=True)
    collection: Mapped[str] = Column(TEXT)

    __table_args__ = (
        Index(LineRunIndexName.RUN_LINE_NUMBER, "run", "line_number"),
        Index(LineRunIndexName.PARENT_ID, "parent_id"),
        Index(LineRunIndexName.COLLECTION, "collection"),
        Index(LineRunIndexName.RUN, "run"),
        Index(LineRunIndexName.EXPERIMENT, "experiment"),
        Index(LineRunIndexName.TRACE_ID, "trace_id"),
        Index(LineRunIndexName.SESSION_ID, "session_id"),
    )

    @sqlite_retry
    def persist(self) -> None:
        with trace_mgmt_db_session() as session:
            session.merge(self)
            session.commit()

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

    @staticmethod
    @sqlite_retry
    def list(
        collection: typing.Optional[str] = None,
        runs: typing.Optional[typing.List[str]] = None,
        experiments: typing.Optional[typing.List[str]] = None,
        trace_ids: typing.Optional[typing.List[str]] = None,
        session_id: typing.Optional[str] = None,
        line_run_ids: typing.Optional[typing.List[str]] = None,
    ) -> typing.List["LineRun"]:
        with trace_mgmt_db_session() as session:
            query = session.query(LineRun)
            if collection is not None:
                query = query.filter(LineRun.collection == collection)
            elif runs is not None:
                query = query.filter(LineRun.run.in_(runs))
            elif experiments is not None:
                query = query.filter(LineRun.experiment.in_(experiments))
            elif trace_ids is not None:
                query = query.filter(LineRun.trace_id.in_(trace_ids))
            elif line_run_ids is not None:
                query = query.filter(LineRun.line_run_id.in_(line_run_ids))
            elif session_id is not None:
                query = query.filter(LineRun.session_id == session_id)
            query = query.order_by(LineRun.start_time.desc())
            if collection is not None:
                query = query.limit(TRACE_LIST_DEFAULT_LIMIT)
            return query.all()

    @staticmethod
    @sqlite_retry
    def search(expression: str, limit: typing.Optional[int] = None) -> typing.List["LineRun"]:
        with trace_mgmt_db_session() as session:
            translator = SearchTranslator(model=LineRun)
            query = translator.translate(session=session, expression=expression)
            return query.all() if limit is None else query.limit(limit).all()

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

    @staticmethod
    @sqlite_retry
    def _get_children(line_run_id: str) -> typing.List["LineRun"]:
        with trace_mgmt_db_session() as session:
            line_runs = session.query(LineRun).filter(LineRun.parent_id == line_run_id).all()
            return line_runs


LINE_RUN_SEARCHABLE_FIELDS = [
    "name",
    "kind",
    "status",
    "start_time",
    # tokens -> cumulative_token_count
    "total",
    "prompt",
    "completion",
    # filter
    "collection",
    "run",
    "session_id",
]
LINE_RUN_JSON_FIELDS = {
    "total": "cumulative_token_count",
    "prompt": "cumulative_token_count",
    "completion": "cumulative_token_count",
}


@dataclass
class SearchTransStackItem:
    orm_op: typing.Union[sqlalchemy.and_, sqlalchemy.or_]
    expected_length: int
    conditions: typing.List[sqlalchemy.text]

    def append_condition(self, condition: sqlalchemy.text) -> None:
        self.conditions.append(condition)

    @property
    def is_full(self) -> bool:
        return len(self.conditions) == self.expected_length

    @property
    def orm_condition(self):
        return self.orm_op(*self.conditions)


class SearchTranslator(ast.NodeVisitor):
    """Translate line run search to SQLite query."""

    LINE_RUN_SEARCHABLE_FIELDS = [
        "name",
        "kind",
        "status",
        "start_time",
        # token count
        "cumulative_token_count.total",
        "cumulative_token_count.prompt",
        "cumulative_token_count.completion",
        # kind of syntax sugar: hide cumulative_token_count
        "total",
        "prompt",
        "completion",
        # filter
        "collection",
        "run",
        "session_id",
    ]
    LINE_RUN_JSON_FIELDS = {
        "total": "cumulative_token_count",
        "prompt": "cumulative_token_count",
        "completion": "cumulative_token_count",
    }

    def __init__(self, model):
        self._model = model
        # for query build during AST traversal
        self._stack: typing.List[SearchTransStackItem] = list()
        self._orm_condition_from_ast = None
        self._searched_json_fields = set()

    def _build_query(self, session: Session) -> Query:
        query = session.query(self._model)
        # if no JSON field is queried, directly build the query
        if len(self._searched_json_fields) == 0:
            return query.filter(self._orm_condition_from_ast)
        # otherwise, manually append "IS NOT NULL"
        orm_conditions = [self._orm_condition_from_ast]
        for field in self._searched_json_fields:
            orm_conditions.append(sqlalchemy.text(f"{field} IS NOT NULL"))
        return query.filter(sqlalchemy.and_(*orm_conditions))

    def translate(self, session: Session, expression: str) -> Query:
        # parse expression to AST
        try:
            tree = ast.parse(expression, mode="eval")
            # expression like "name" is not valid
            assert isinstance(tree.body, (ast.Compare, ast.BoolOp))
        except (SyntaxError, AssertionError):
            error_message = "Invalid search expression, currently support Python syntax for search."
            raise WrongTraceSearchExpressionError(error_message)
        # traverse the AST and validate the fields are searchable
        # leveraging `ast.NodeVisitor.visit`
        self.visit(tree.body)
        return self._build_query(session=session)

    # override visit BoolOp and Compare methods
    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # for bool op:
        #   1. translate op to ORM op
        #   2. push ORM op, #values and an empty list to the stack
        # currently we support `and` and `or`
        if isinstance(node.op, ast.And):
            orm_op = sqlalchemy.and_
        elif isinstance(node.op, ast.Or):
            orm_op = sqlalchemy.or_
        else:
            error_message = "Unsupported bool operator, currently support: 'and', 'or'."
            raise WrongTraceSearchExpressionError(error_message)
        stack_item = SearchTransStackItem(orm_op=orm_op, expected_length=len(node.values), conditions=list())
        self._stack.append(stack_item)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        # for compare
        #   1. translate compare to SQL condition
        #   2. append SQL condition to top item of the stack
        #   3. while the top item is full, pop it, translate to ORM condition and push back
        #   4. apply ORM condition to the query if the stack is empty
        sql_condition = self._translate_compare_to_sql(node)
        sql_condition = sqlalchemy.text(sql_condition)
        if len(self._stack) == 0:
            self._orm_condition_from_ast = sql_condition
            self.generic_visit(node)
            return
        self._stack[-1].append_condition(sql_condition)
        while len(self._stack) > 0 and self._stack[-1].is_full:
            top_item = self._stack.pop()
            if len(self._stack) == 0:
                self._orm_condition_from_ast = top_item.orm_condition
            else:
                self._stack[-1].append_condition(top_item.orm_condition)
        self.generic_visit(node)
        return

    def _resolve_ast_node(self, node: typing.Union[ast.Attribute, ast.Constant, ast.Name]) -> str:
        if isinstance(node, ast.Attribute):
            ast_name = ast.Name(id=f"{node.value.id}.{node.attr}")
            return self._resolve_ast_name(ast_name)
        elif isinstance(node, ast.Constant):
            return self._resolve_ast_constant(node)
        elif isinstance(node, ast.Name):
            return self._resolve_ast_name(node)
        else:
            error_message = (
                "Currently only support simple compare expression, e.g., 'name == \"my_llm\"', "
                "or combined with 'and' and 'or', e.g., 'name == \"my_llm\" and 100 < total <= 200'."
            )
            raise WrongTraceSearchExpressionError(error_message)

    def _resolve_ast_constant(self, node: ast.Constant) -> str:
        value = node.value
        return f"'{value}'" if isinstance(value, str) else str(value)

    def _resolve_ast_name(self, node: ast.Name) -> str:
        def _handle_json_field(_field: str, _parent_field: str) -> str:
            # we need to record which JSON field(s) queried as we need to apply a final not null
            self._searched_json_fields.add(_parent_field)
            return f"json_extract({_parent_field}, '$.{_field}')"

        field = node.id
        if field not in self.LINE_RUN_SEARCHABLE_FIELDS:
            raise Exception(f"field {field!r} is not searchable")
        if field not in self.LINE_RUN_JSON_FIELDS:
            # if "." exist in field, it is a JSON field, so need to parse field and its parent field
            if "." in field:
                parent_field, field = field.split(".")
                return _handle_json_field(field, parent_field)
            return field
        parent_field = self.LINE_RUN_JSON_FIELDS[field]
        return _handle_json_field(field, parent_field)

    @staticmethod
    def _resolve_ast_op(ast_op: ast.cmpop) -> str:
        if isinstance(ast_op, ast.Eq):
            return "="
        elif isinstance(ast_op, ast.NotEq):
            return "!="
        elif isinstance(ast_op, ast.Lt):
            return "<"
        elif isinstance(ast_op, ast.LtE):
            return "<="
        elif isinstance(ast_op, ast.Gt):
            return ">"
        elif isinstance(ast_op, ast.GtE):
            return ">="
        else:
            error_message = "Unsupported compare operator, currently support: '==', '!=', '<', '<=', '>' and '>='."
            raise WrongTraceSearchExpressionError(error_message)

    def _translate_compare_to_sql(self, node: ast.Compare) -> str:
        left = self._resolve_ast_node(node.left)
        sql_ops, sql_comparators = list(), list()
        for i in range(len(node.ops)):
            ast_op, ast_comparator = node.ops[i], node.comparators[i]
            sql_ops.append(self._resolve_ast_op(ast_op))
            sql_comparators.append(self._resolve_ast_node(ast_comparator))
        # status
        if left == "status" or "status" in sql_comparators:
            left, sql_comparators = self._refine_comparators_for_status(left, sql_comparators)
        # start_time
        if left == "start_time" or "start_time" in sql_comparators:
            left, sql_comparators = self._refine_comparators_for_start_time(left, sql_comparators)
        # finally concat to build the SQL
        sql = left
        for i in range(len(sql_ops)):
            sql += f" {sql_ops[i]} {sql_comparators[i]}"
        return sql

    # special logic to be compatible with UX query
    @staticmethod
    def _refine_comparators_for_status(
        left: str,
        comparators: typing.List[str],
    ) -> typing.Tuple[str, typing.List[str]]:
        # UX renders OTel status 'Ok' as 'complete'
        # so we need to replace that to 'Ok' before query to SQLite
        def _convert_complete_to_ok(_comparator: str) -> str:
            if _comparator == "'complete'":
                return "'Ok'"
            return _comparator

        new_left = _convert_complete_to_ok(left)
        new_comparators = [_convert_complete_to_ok(comparator) for comparator in comparators]
        return new_left, new_comparators

    @staticmethod
    def _refine_comparators_for_start_time(
        left: str,
        comparators: typing.List[str],
    ) -> typing.Tuple[str, typing.List[str]]:
        # we should not suppose user can write standard ISO format time string
        # so we need to apply an internal conversion before query to SQLite
        def _convert_time_string_to_iso(_comparator: str) -> str:
            if _comparator == "start_time":
                return _comparator
            try:
                dt = parse(_comparator)
                return f"'{dt.isoformat()}'"
            except ValueError:
                error_message = f"Invalid time format: {_comparator}"
                raise WrongTraceSearchExpressionError(error_message)

        new_left = _convert_time_string_to_iso(left)
        new_comparators = [_convert_time_string_to_iso(comparator) for comparator in comparators]
        return new_left, new_comparators
