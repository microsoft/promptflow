# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import typing
from dataclasses import asdict, dataclass

from flask import Response, render_template

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("ui", description="UI")

# parsers for query parameters
trace_parser = api.parser()
trace_parser.add_argument("session", type=str, required=False)


# use @dataclass for strong type
@dataclass
class TraceUIParser:
    session_id: typing.Optional[str] = None

    @staticmethod
    def from_request() -> "TraceUIParser":
        args = trace_parser.parse_args()
        return TraceUIParser(
            session_id=args.session,
        )


@api.route("/traces")
class TraceUI(Resource):
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = TraceUIParser.from_request()
        line_runs = client._traces.list_line_runs(
            session_id=args.session_id,
        )
        spans = client._traces.list_spans(
            session_id=args.session_id,
        )
        main_spans, eval_spans = [], []
        for span in spans:
            attributes = span._content[SpanFieldName.ATTRIBUTES]
            if SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes:
                eval_spans.append(span)
            else:
                main_spans.append(span)

        summaries = [asdict(line_run) for line_run in line_runs]
        trace_ui_dict = {
            "summaries": summaries,
            "traces": [span._content for span in main_spans],
            "evaluation_traces": [span._content for span in eval_spans],
        }

        # concat data for rendering dummy UI
        summary = [
            {
                "trace_id": line_run.line_run_id,
                "content": json.dumps(asdict(line_run), indent=4),
            }
            for line_run in line_runs
        ]
        traces = [
            {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "content": json.dumps(span._content, indent=4),
            }
            for span in main_spans
        ]
        eval_traces = [
            {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "content": json.dumps(span._content, indent=4),
            }
            for span in eval_spans
        ]

        return Response(
            render_template(
                "ui_traces.html",
                trace_ui_dict=json.dumps(trace_ui_dict),
                summary=summary,
                traces=traces,
                eval_traces=eval_traces,
            ),
            mimetype="text/html",
        )
