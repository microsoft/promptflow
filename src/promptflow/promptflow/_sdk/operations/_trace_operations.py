# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing

from promptflow._sdk._orm.trace import LineRun as ORMLineRun
from promptflow._sdk._orm.trace import Span as ORMSpan
from promptflow._sdk.entities._trace import LineRun, Span


class TraceOperations:
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

    def list_spans(self, trace_ids: typing.Union[str, typing.List[str]]) -> typing.List[Span]:
        if isinstance(trace_ids, str):
            trace_ids = [trace_ids]
        return [Span._from_orm_object(obj) for obj in ORMSpan.list(trace_ids=trace_ids)]

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
        return line_runs
