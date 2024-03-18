# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import typing
from collections import defaultdict

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import LineRun, Span
from promptflow._utils.logger_utils import get_cli_sdk_logger

_logger = get_cli_sdk_logger()


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

    def get_line_run(self, line_run_id: str) -> LineRun:
        orm_spans = ORMLineRun.get_line_run(line_run_id=line_run_id)
        line_run = LineRun._from_spans(
            spans=[Span._from_orm_object(orm_span) for orm_span in orm_spans],
            trace_id=line_run_id,
        )
        return line_run

    def list_line_runs(
        self,
        session_id: typing.Optional[str] = None,
        runs: typing.Optional[typing.List[str]] = None,
        experiments: typing.Optional[typing.List[str]] = None,
        trace_ids: typing.Optional[typing.List[str]] = None,
    ) -> typing.List[LineRun]:
        if runs is not None:
            return self._list_line_runs_with_runs(runs)
        if trace_ids is not None:
            line_runs = list()
            for trace_id in trace_ids:
                line_run = self.get_line_run(trace_id)
                if line_run is not None:
                    line_runs.append(line_run)
            return line_runs

        orm_spans_group_by_trace_id = ORMLineRun.list(
            session_id=session_id,
            experiments=experiments,
        )
        # ORM entities to SDK entities
        spans_group_by_trace_id = list()
        for orm_spans in orm_spans_group_by_trace_id:
            spans_group_by_trace_id.append([Span._from_orm_object(orm_span) for orm_span in orm_spans])
        aggregated_spans = self._aggregate_spans(spans_group_by_trace_id)
        line_runs = list()
        for line_run_spans in aggregated_spans:
            line_run = LineRun._from_spans(line_run_spans)
            if line_run is not None:
                line_runs.append(line_run)
        return line_runs

    @staticmethod
    def _aggregate_spans(spans: typing.List[typing.List[Span]]) -> typing.List[typing.List[Span]]:
        # the input of this function is a list of span lists, each shares the same trace id
        # this function targets to aggregate those with lineage relationship
        # so that the output is still a list of span lists, but each represents a line run
        aggregated_spans = defaultdict(list)
        for trace_id_spans in spans:
            # as spans with same trace id also have same key attributes to group
            # select the first span on behalf of the list
            obo_span = trace_id_spans[0]
            obo_attrs = obo_span._content[SpanFieldName.ATTRIBUTES]

            if (
                SpanAttributeFieldName.LINE_RUN_ID not in obo_attrs
                and SpanAttributeFieldName.BATCH_RUN_ID not in obo_attrs
            ):
                # standard OpenTelemetry traces
                # or simply traces without prompt flow attributes (e.g., aggregation node in batch run)
                aggregated_spans[obo_span.trace_id] = copy.deepcopy(trace_id_spans)
            elif (
                SpanAttributeFieldName.LINE_RUN_ID in obo_attrs and SpanAttributeFieldName.BATCH_RUN_ID not in obo_attrs
            ):
                # test scenario
                line_run_key = obo_attrs[SpanAttributeFieldName.LINE_RUN_ID]
                # if traces come from eval flow, use `referenced.line_run_id` as the line run key
                if SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in obo_attrs:
                    line_run_key = obo_attrs[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
                aggregated_spans[line_run_key].extend(copy.deepcopy(trace_id_spans))
            elif (
                SpanAttributeFieldName.LINE_RUN_ID not in obo_attrs and SpanAttributeFieldName.BATCH_RUN_ID in obo_attrs
            ):
                # batch run scenario
                batch_run_id = obo_attrs[SpanAttributeFieldName.BATCH_RUN_ID]
                line_number = obo_attrs[SpanAttributeFieldName.LINE_NUMBER]
                # if traces come from eval flow, use `referenced.batch_run_id` as the batch run id
                if SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID in obo_attrs:
                    batch_run_id = obo_attrs[SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID]
                # batch run line run should consider both batch run id and line number
                line_run_key = f"{batch_run_id}.{line_number}"
                aggregated_spans[line_run_key].extend(copy.deepcopy(trace_id_spans))
            else:
                # invalid traces, `LINE_RUN_ID` and `BATCH_RUN_ID` should not appear at the same time
                warning_message = (
                    f"Invalid traces found, trace id: {obo_span.trace_id}, "
                    "`LINE_RUN_ID` and `BATCH_RUN_ID` should not appear at the same time."
                )
                _logger.warning(warning_message)
        # convert dict to list
        return list(aggregated_spans.values())

    def _list_line_runs_with_runs(self, runs: typing.List[str]) -> typing.List[LineRun]:
        orm_spans_group_by_trace_id = ORMLineRun.list_with_runs(runs)
        # ORM entities to SDK entities
        spans_group_by_trace_id = list()
        for orm_spans in orm_spans_group_by_trace_id:
            spans_group_by_trace_id.append([Span._from_orm_object(orm_span) for orm_span in orm_spans])
        # aggregation logic is different when runs are specified
        # so will not call `_aggregate_spans` here
        grouped_spans = {run: defaultdict(list) for run in runs}
        for trace_id_spans in spans_group_by_trace_id:
            # as spans with same trace id also have same key attributes to group
            # select the first span on behalf of the list
            obo_span: Span = trace_id_spans[0]
            obo_attrs = obo_span._content[SpanFieldName.ATTRIBUTES]
            # aggregation node will not have `batch_run_id`, ignore
            if SpanAttributeFieldName.BATCH_RUN_ID not in obo_attrs:
                continue
            batch_run_id = obo_attrs[SpanAttributeFieldName.BATCH_RUN_ID]
            line_number = obo_attrs[SpanAttributeFieldName.LINE_NUMBER]
            # check if it is an evaluation root span
            if SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID in obo_attrs:
                referenced_batch_run_id = obo_attrs[SpanAttributeFieldName.REFERENCED_BATCH_RUN_ID]
                if referenced_batch_run_id in runs:
                    grouped_spans[referenced_batch_run_id][line_number].extend(copy.deepcopy(trace_id_spans))
                    continue
            grouped_spans[batch_run_id][line_number].extend(copy.deepcopy(trace_id_spans))
        line_runs = list()
        for run in grouped_spans:
            run_spans = grouped_spans[run]
            if len(run_spans) == 0:
                continue
            for line_number in run_spans:
                line_spans = run_spans[line_number]
                line_run = LineRun._from_spans(line_spans, run=run)
                if line_run is not None:
                    line_runs.append(line_run)
        return line_runs
