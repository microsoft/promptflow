# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import logging
import typing

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan
from opentelemetry.trace.span import format_span_id, format_trace_id

from promptflow._constants import (
    SpanContextFieldName,
    SpanEventFieldName,
    SpanFieldName,
    SpanLinkFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import TRACE_DEFAULT_COLLECTION
from promptflow._sdk._orm.retry import sqlite_retry
from promptflow._sdk._orm.session import trace_mgmt_db_session
from promptflow._sdk._orm.trace import Event as ORMEvent
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk._telemetry import ActivityType, monitor_operation
from promptflow._sdk._utils import (
    convert_time_unix_nano_to_timestamp,
    flatten_pb_attributes,
    parse_otel_span_status_code,
)
from promptflow._sdk.entities._trace import Event, LineRun, Span
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException


class TraceOperations:
    def __init__(self):
        self._logger = get_cli_sdk_logger()

    def _parse_protobuf_events(obj: typing.List[PBSpan.Event], logger: logging.Logger) -> typing.List[typing.Dict]:
        events = []
        if len(obj) == 0:
            logger.debug("No events found in span")
            return events
        for pb_event in obj:
            event_dict: dict = json.loads(MessageToJson(pb_event))
            logger.debug("Received event: %s", json.dumps(event_dict))
            event = {
                SpanEventFieldName.NAME: pb_event.name,
                # .isoformat() here to make this dumpable to JSON
                SpanEventFieldName.TIMESTAMP: convert_time_unix_nano_to_timestamp(pb_event.time_unix_nano).isoformat(),
                SpanEventFieldName.ATTRIBUTES: flatten_pb_attributes(
                    event_dict.get(SpanEventFieldName.ATTRIBUTES, dict())
                ),
            }
            events.append(event)
        return events

    @staticmethod
    def _parse_protobuf_links(obj: typing.List[PBSpan.Link], logger: logging.Logger) -> typing.List[typing.Dict]:
        links = []
        if len(obj) == 0:
            logger.debug("No links found in span")
            return links
        for pb_link in obj:
            link_dict: dict = json.loads(MessageToJson(pb_link))
            logger.debug("Received link: %s", json.dumps(link_dict))
            link = {
                SpanLinkFieldName.CONTEXT: {
                    SpanContextFieldName.TRACE_ID: TraceOperations.format_trace_id(pb_link.trace_id),
                    SpanContextFieldName.SPAN_ID: TraceOperations.format_span_id(pb_link.span_id),
                    SpanContextFieldName.TRACE_STATE: pb_link.trace_state,
                },
                SpanLinkFieldName.ATTRIBUTES: flatten_pb_attributes(
                    link_dict.get(SpanLinkFieldName.ATTRIBUTES, dict())
                ),
            }
            links.append(link)
        return links

    @staticmethod
    def format_span_id(span_id: bytes) -> str:
        """Format span id to hex string.
        Note that we need to add 0x since it is how opentelemetry-sdk does.
        Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
        642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
        """
        return f"0x{format_span_id(int.from_bytes(span_id, byteorder='big', signed=False))}"

    @staticmethod
    def format_trace_id(trace_id: bytes) -> str:
        """Format trace_id id to hex string.
        Note that we need to add 0x since it is how opentelemetry-sdk does.
        Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
        642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
        """
        return f"0x{format_trace_id(int.from_bytes(trace_id, byteorder='big', signed=False))}"

    @staticmethod
    def _parse_protobuf_span(span: PBSpan, resource: typing.Dict, logger: logging.Logger) -> Span:
        # Open Telemetry does not provide official way to parse Protocol Buffer Span object
        # so we need to parse it manually relying on `MessageToJson`
        # reference: https://github.com/open-telemetry/opentelemetry-python/issues/3700#issuecomment-2010704554
        span_dict: dict = json.loads(MessageToJson(span))
        logger.debug("Received span: %s, resource: %s", json.dumps(span_dict), json.dumps(resource))
        span_id = TraceOperations.format_span_id(span.span_id)
        trace_id = TraceOperations.format_trace_id(span.trace_id)
        parent_id = TraceOperations.format_span_id(span.parent_span_id) if span.parent_span_id else None
        # we have observed in some scenarios, there is not `attributes` field
        attributes = flatten_pb_attributes(span_dict.get(SpanFieldName.ATTRIBUTES, dict()))
        logger.debug("Parsed attributes: %s", json.dumps(attributes))
        links = TraceOperations._parse_protobuf_links(span.links, logger)
        events = TraceOperations._parse_protobuf_events(span.events, logger)

        return Span(
            trace_id=trace_id,
            span_id=span_id,
            name=span.name,
            context={
                SpanContextFieldName.TRACE_ID: trace_id,
                SpanContextFieldName.SPAN_ID: span_id,
                SpanContextFieldName.TRACE_STATE: span.trace_state,
            },
            kind=span.kind,
            parent_id=parent_id if parent_id else None,
            start_time=convert_time_unix_nano_to_timestamp(span.start_time_unix_nano),
            end_time=convert_time_unix_nano_to_timestamp(span.end_time_unix_nano),
            status={
                SpanStatusFieldName.STATUS_CODE: parse_otel_span_status_code(span.status.code),
                SpanStatusFieldName.DESCRIPTION: span.status.message,
            },
            attributes=attributes,
            links=links,
            events=events,
            resource=resource,
        )

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
