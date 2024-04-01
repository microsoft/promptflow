# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import typing

from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._orm.trace import Event as ORMEvent
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow._sdk.entities._trace import Event, LineRun, Span
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

    def list_line_runs(
        self,
        collection: typing.Optional[str] = None,
        runs: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        experiments: typing.Optional[typing.Union[str, typing.List[str]]] = None,
        trace_ids: typing.Optional[typing.Union[str, typing.List[str]]] = None,
    ) -> typing.List[LineRun]:
        # ensure runs, experiments, and trace_ids are list of string
        if isinstance(runs, str):
            runs = [runs]
        if isinstance(experiments, str):
            experiments = [experiments]
        if isinstance(trace_ids, str):
            trace_ids = [trace_ids]

        # currently we list parent line runs first, and query children for each
        # this will query SQLite for N+1 times (N is the number of parent line runs)
        # which is not efficient and is possible to optimize this
        orm_line_runs = ORMLineRun.list(
            collection=collection,
            runs=runs,
            experiments=experiments,
            trace_ids=trace_ids,
        )
        line_runs = []
        for obj in orm_line_runs:
            line_run = LineRun._from_orm_object(obj)
            orm_eval_line_runs = ORMLineRun._get_children(line_run_id=line_run.line_run_id)
            eval_line_runs = [LineRun._from_orm_object(obj) for obj in orm_eval_line_runs]
            line_run._append_evaluations(eval_line_runs)
            line_runs.append(line_run)
        return line_runs

    @monitor_operation(activity_name="pf.traces.delete", activity_type=ActivityType.PUBLICAPI)
    def delete(
        self,
        run: typing.Optional[str] = None,
        collection: typing.Optional[str] = None,
        started_before: typing.Optional[typing.Union[str, datetime.datetime]] = None,
    ) -> None:
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
        """
        self._logger.debug(
            "delete traces with parameters, run: %s, collection: %s, started_before: %s",
            run,
            collection,
            started_before,
        )
        self._validate_delete_query_params(run=run, collection=collection, started_before=started_before)
        self._logger.debug("try to delete line run(s)...")
        if isinstance(started_before, str):
            started_before = datetime.datetime.fromisoformat(started_before)
        line_run_cnt, trace_ids = ORMLineRun.delete(
            run=run,
            collection=collection,
            started_before=started_before,
        )
        self._logger.debug("deleted %d line runs", line_run_cnt)
        self._logger.debug("try to delete traces and events for trace_ids: %s", trace_ids)
        span_cnt = ORMSpan.delete(trace_ids=trace_ids)
        event_cnt = ORMEvent.delete(trace_ids=trace_ids)
        self._logger.debug("deleted %d spans and %d events", span_cnt, event_cnt)
        return

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
        raise UserErrorException(error_message)
