# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import typing

from promptflow._sdk._constants import (
    TRACE_COLLECTION_LIST_DEFAULT_LIMIT,
    TRACE_DEFAULT_COLLECTION,
    TRACE_LIST_DEFAULT_LIMIT,
)
from promptflow._sdk._orm.retry import sqlite_retry
from promptflow._sdk._orm.session import trace_mgmt_db_session
from promptflow._sdk._orm.trace import Event as ORMEvent
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow._sdk._utilities.tracing_utils import append_conditions
from promptflow._sdk.entities._trace import Collection, Event, LineRun, Span
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException


class TraceOperations:
    def __init__(self):
        self._logger = get_cli_sdk_logger()

    def get_event(self, event_id: str) -> typing.Dict:
        return Event.get(event_id=event_id)

    def get_span(
        self,
        span_id: str,
        trace_id: typing.Optional[str] = None,
        lazy_load: bool = True,
    ) -> Span:
        orm_span = ORMSpan.get(span_id=span_id, trace_id=trace_id)
        span = Span._from_orm_object(orm_span)
        if not lazy_load:
            span._load_events()
        return span

    def list_spans(
        self,
        trace_ids: typing.Union[str, typing.List[str]],
        lazy_load: bool = True,
    ) -> typing.List[Span]:
        if isinstance(trace_ids, str):
            trace_ids = [trace_ids]
        orm_spans = ORMSpan.list(trace_ids=trace_ids)
        spans = []
        for obj in orm_spans:
            span = Span._from_orm_object(obj)
            if not lazy_load:
                span._load_events()
            spans.append(span)
        return spans

    def get_line_run(self, line_run_id: str) -> LineRun:
        orm_line_run = ORMLineRun.get(line_run_id=line_run_id)
        line_run = LineRun._from_orm_object(orm_line_run)
        orm_eval_line_runs = ORMLineRun._get_children(line_run_id=line_run_id)
        eval_line_runs = [LineRun._from_orm_object(obj) for obj in orm_eval_line_runs]
        line_run._append_evaluations(eval_line_runs)
        return line_run

    def _parse_line_runs_from_orm(self, orm_line_runs: typing.List[ORMLineRun]) -> typing.List[LineRun]:
        line_runs = []
        for obj in orm_line_runs:
            line_run = LineRun._from_orm_object(obj)
            orm_eval_line_runs = ORMLineRun._get_children(line_run_id=line_run.line_run_id)
            eval_line_runs = [LineRun._from_orm_object(obj) for obj in orm_eval_line_runs]
            line_run._append_evaluations(eval_line_runs)
            line_runs.append(line_run)
        return line_runs

    def list_line_runs(
        self,
        collection: typing.Optional[str] = None,
        runs: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        experiments: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        trace_ids: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        session_id: typing.Optional[str] = None,
        line_run_ids: typing.Optional[typing.Union[str, typing.List[str]]] = None,
    ) -> typing.List[LineRun]:
        # ensure runs, experiments, and trace_ids are list of string
        if isinstance(runs, str):
            runs = [runs]
        if isinstance(experiments, str):
            experiments = [experiments]
        if isinstance(trace_ids, str):
            trace_ids = [trace_ids]
        if isinstance(line_run_ids, str):
            line_run_ids = [line_run_ids]

        # currently we list parent line runs first, and query children for each
        # this will query SQLite for N+1 times (N is the number of parent line runs)
        # which is not efficient and is possible to optimize this
        orm_line_runs = ORMLineRun.list(
            collection=collection,
            runs=runs,
            experiments=experiments,
            trace_ids=trace_ids,
            session_id=session_id,
            line_run_ids=line_run_ids,
        )
        return self._parse_line_runs_from_orm(orm_line_runs)

    def _search_line_runs(
        self,
        expression: str,
        collection: typing.Optional[str] = None,
        runs: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        session_id: typing.Optional[str] = None,
    ) -> typing.List[LineRun]:
        expression = append_conditions(
            expression=expression,
            collection=collection,
            runs=runs,
            session_id=session_id,
            logger=self._logger,
        )
        self._logger.info("search expression that will be executed: %s", expression)
        # when neither collection, runs nor session_id is specified, we will add a limit for the query
        # avoid returning too many results
        limit = None
        if collection is None and runs is None and session_id is None:
            limit = TRACE_LIST_DEFAULT_LIMIT
            self._logger.info("apply a default limit for the search: %d", limit)
        orm_line_runs = ORMLineRun.search(expression, limit=limit)
        return self._parse_line_runs_from_orm(orm_line_runs)

    @monitor_operation(activity_name="pf.traces.delete", activity_type=ActivityType.PUBLICAPI)
    def delete(
        self,
        run: typing.Optional[str] = None,
        collection: typing.Optional[str] = None,
        started_before: typing.Optional[typing.Union[str, datetime.datetime]] = None,
        **kwargs,
    ) -> int:
        """Delete traces permanently.

        Support delete according to:
          - run
          - non default collection
          - collection combined with time as started before

        Examples:
          - pf.traces.delete(run="name")
          - pf.traces.delete(collection="collection")
          - pf.traces.delete(collection="default", started_before="2024-03-19T15:17:23.807563")

        :param run: Name of the run.
        :type run: Optional[str]
        :param session: Id of the session.
        :type session: Optional[str]
        :param started_before: ISO 8601 format time string (e.g., "2024-03-19T15:17:23.807563").
        :type started_before: Optional[Union[str, datetime.datetime]]
        :param dry_run: If True, will not perform real deletion.
        :type dry_run: bool
        :return: Number of traces to delete, only return in dry run mode.
        :rtype: int
        """
        dry_run = kwargs.get("dry_run", False)
        self._logger.debug(
            "delete traces with parameters, run: %s, collection: %s, started_before: %s",
            run,
            collection,
            started_before,
        )
        self._validate_delete_query_params(run=run, collection=collection, started_before=started_before)
        if dry_run:
            self._logger.debug("dry run mode, will not perform real deletion...")
        else:
            self._logger.debug("try to delete traces...")
        if isinstance(started_before, str):
            started_before = datetime.datetime.fromisoformat(started_before)
        return self._delete_within_transaction(
            run=run, collection=collection, started_before=started_before, dry_run=dry_run
        )

    def _validate_delete_query_params(
        self,
        run: typing.Optional[str] = None,
        collection: typing.Optional[str] = None,
        started_before: typing.Optional[typing.Union[str, datetime.datetime]] = None,
    ) -> None:
        # valid delete queries:
        #   1. run=xxx
        #   2. collection=yyy
        #   3. collection=zz, started_before=zz
        # this function will directly return for valid cases
        if run is not None and collection is None and started_before is None:
            return
        if collection is not None and run is None:
            if started_before is not None:
                # if `started_before` is a time string, need to ensure it's in valid ISO 8601 format
                if isinstance(started_before, str):
                    try:
                        datetime.datetime.fromisoformat(started_before)
                        return
                    except ValueError:
                        pass
                elif isinstance(started_before, datetime.datetime):
                    return
            elif collection != TRACE_DEFAULT_COLLECTION:
                return
        error_message = (
            'Valid delete queries: 1) specify `run`; 2) specify `collection` (not "default"); '
            "3) specify `collection` and `started_before` (ISO 8601)."
        )
        self._logger.error(error_message)
        raise UserErrorException(error_message)

    @sqlite_retry
    def _delete_within_transaction(
        self,
        run: typing.Optional[str] = None,
        collection: typing.Optional[str] = None,
        started_before: typing.Optional[datetime.datetime] = None,
        dry_run: bool = False,
    ) -> int:
        # delete will occur across 3 tables: line_runs, spans and events
        # which be done in a transaction
        from sqlalchemy.orm import Query

        with trace_mgmt_db_session() as session:
            # query line run first to get all trace ids
            query: Query = session.query(ORMLineRun)
            if run is not None:
                query = query.filter(ORMLineRun.run == run)
            if collection is not None:
                query = query.filter(ORMLineRun.collection == collection)
            if started_before is not None:
                query = query.filter(ORMLineRun.start_time < started_before)
            trace_ids = [line_run.trace_id for line_run in query.all()]

            if dry_run:
                return len(trace_ids)

            self._logger.debug("try to delete traces for trace_ids: %s", trace_ids)
            # deletes happen
            event_cnt = session.query(ORMEvent).filter(ORMEvent.trace_id.in_(trace_ids)).delete()
            span_cnt = session.query(ORMSpan).filter(ORMSpan.trace_id.in_(trace_ids)).delete()
            line_run_cnt = query.delete()
            session.commit()
        self._logger.debug("deleted %d line runs, %d spans, and %d events", line_run_cnt, span_cnt, event_cnt)
        return len(trace_ids)

    @sqlite_retry
    def _list_collections(self, limit: typing.Optional[int] = None) -> typing.List[Collection]:
        from sqlalchemy import func

        if limit is None:
            self._logger.debug("use default limit %d for collection list", TRACE_COLLECTION_LIST_DEFAULT_LIMIT)
            limit = TRACE_COLLECTION_LIST_DEFAULT_LIMIT
        with trace_mgmt_db_session() as session:
            subquery = (
                session.query(
                    ORMLineRun.collection,
                    func.max(ORMLineRun.start_time).label("max_start_time"),
                )
                .group_by(ORMLineRun.collection)
                .subquery()
            )
            results = (
                session.query(subquery.c.collection, subquery.c.max_start_time)
                .order_by(subquery.c.max_start_time.desc())
                .limit(limit)
                .all()
            )
        return [Collection(name, update_time) for name, update_time in results]
