# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
import typing

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import LineRun, Span


class TraceOperations:
    def list_spans(
        self,
        session_id: typing.Optional[str] = None,
        trace_ids: typing.Optional[typing.List[str]] = None,
    ) -> typing.List[Span]:
        orm_spans = ORMSpan.list(
            session_id=session_id,
            trace_ids=trace_ids,
        )
        return [Span._from_orm_object(orm_span) for orm_span in orm_spans]

    def list_line_runs(
        self,
        session_id: typing.Optional[str] = None,
        runs: typing.Optional[typing.List[str]] = None,
        experiments: typing.Optional[typing.List[str]] = None,
    ) -> typing.List[LineRun]:
        # separate query with runs
        if runs is not None:
            return self._list_line_runs_with_runs(runs)

        line_runs = []
        orm_spans_group_by_trace_id = ORMLineRun.list(
            session_id=session_id,
            experiments=experiments,
        )
        # merge spans with same `line_run_id` or `referenced.line_run_id` (if exists)
        grouped_orm_spans = {}
        for orm_spans in orm_spans_group_by_trace_id:
            first_orm_span = orm_spans[0]
            attributes = json.loads(first_orm_span.content)[SpanFieldName.ATTRIBUTES]
            if (
                SpanAttributeFieldName.LINE_RUN_ID not in attributes
                and SpanAttributeFieldName.BATCH_RUN_ID not in attributes
            ):
                # standard OpenTelemetry trace, regard as a line run
                grouped_orm_spans[first_orm_span.trace_id] = copy.deepcopy(orm_spans)
            elif SpanAttributeFieldName.LINE_RUN_ID in attributes:
                # test scenario
                if SpanAttributeFieldName.REFERENCED_LINE_RUN_ID not in attributes:
                    # main flow
                    line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
                    if line_run_id not in grouped_orm_spans:
                        grouped_orm_spans[line_run_id] = []
                    grouped_orm_spans[line_run_id].extend(copy.deepcopy(orm_spans))
                else:
                    # evaluation flow
                    referenced_line_run_id = attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
                    if referenced_line_run_id not in grouped_orm_spans:
                        grouped_orm_spans[referenced_line_run_id] = []
                    grouped_orm_spans[referenced_line_run_id].extend(copy.deepcopy(orm_spans))
            elif SpanAttributeFieldName.BATCH_RUN_ID in attributes:
                # batch run scenario
                if SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID not in attributes:
                    # main flow
                    line_run_id = (
                        attributes[SpanAttributeFieldName.BATCH_RUN_ID]
                        + "_"
                        + attributes[SpanAttributeFieldName.LINE_NUMBER]
                    )
                    if line_run_id not in grouped_orm_spans:
                        grouped_orm_spans[line_run_id] = []
                    grouped_orm_spans[line_run_id].extend(copy.deepcopy(orm_spans))
                else:
                    # evaluation flow
                    referenced_line_run_id = (
                        attributes[SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID]
                        + "_"
                        + attributes[SpanAttributeFieldName.LINE_NUMBER]
                    )
                    if referenced_line_run_id not in grouped_orm_spans:
                        grouped_orm_spans[referenced_line_run_id] = []
                    grouped_orm_spans[referenced_line_run_id].extend(copy.deepcopy(orm_spans))
            else:
                # others, ignore for now
                pass
        for orm_spans in grouped_orm_spans.values():
            spans = [Span._from_orm_object(orm_span) for orm_span in orm_spans]
            line_run = LineRun._from_spans(spans)
            if line_run is not None:
                line_runs.append(line_run)
        return line_runs

    def _list_line_runs_with_runs(self, runs: typing.List[str]) -> typing.List[LineRun]:
        orm_spans = ORMSpan.list_with_runs(runs)
        # group root spans by lineage:
        #   1. main + eval
        #   2. eval
        grouped_spans = {run: dict() for run in runs}
        for span in map(Span._from_orm_object, orm_spans):
            attributes = span._content[SpanFieldName.ATTRIBUTES]
            # aggregation node will not have `batch_run_id`, ignore
            if SpanAttributeFieldName.BATCH_RUN_ID not in attributes:
                continue
            batch_run_id = attributes[SpanAttributeFieldName.BATCH_RUN_ID]
            line_number = attributes[SpanAttributeFieldName.LINE_NUMBER]
            # check if it is an evaluation root span
            if SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID in attributes:
                referenced_batch_run_id = attributes[SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID]
                if referenced_batch_run_id in runs:
                    if line_number not in grouped_spans[referenced_batch_run_id]:
                        grouped_spans[referenced_batch_run_id][line_number] = []
                    grouped_spans[referenced_batch_run_id][line_number].append(span)
                    continue
            if line_number not in grouped_spans[batch_run_id]:
                grouped_spans[batch_run_id][line_number] = []
            grouped_spans[batch_run_id][line_number].append(span)
        line_runs = []
        for run in grouped_spans:
            run_spans = grouped_spans[run]
            if len(run_spans) == 0:
                continue
            for line_number in run_spans:
                line_spans = run_spans[line_number]
                line_run = LineRun._from_run_and_spans(run, line_spans)
                line_runs.append(line_run)
        return line_runs
