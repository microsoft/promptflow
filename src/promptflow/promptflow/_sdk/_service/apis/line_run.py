# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import asdict, dataclass

from flask_restx import fields

from promptflow._sdk._constants import PFS_MODEL_DATETIME_FORMAT, CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow._sdk.entities._trace import LineRun as LineRunEntity

api = Namespace("LineRuns", description="Line runs management")

# parsers for query parameters
list_line_run_parser = api.parser()
list_line_run_parser.add_argument("session", type=str, required=False)
list_line_run_parser.add_argument("run", type=str, required=False)
list_line_run_parser.add_argument("experiment", type=str, required=False)
list_line_run_parser.add_argument("trace_ids", type=str, required=False)


# use @dataclass for strong type
@dataclass
class ListLineRunParser:
    session_id: typing.Optional[str] = None
    runs: typing.Optional[typing.List[str]] = None
    experiments: typing.Optional[typing.List[str]] = None
    trace_ids: typing.Optional[typing.List[str]] = None

    @staticmethod
    def _parse_string_list(value: typing.Optional[str]) -> typing.Optional[typing.List[str]]:
        if value is None:
            return None
        return value.split(",")

    @staticmethod
    def from_request() -> "ListLineRunParser":
        args = list_line_run_parser.parse_args()
        return ListLineRunParser(
            session_id=args.session,
            runs=ListLineRunParser._parse_string_list(args.run),
            experiments=ListLineRunParser._parse_string_list(args.experiment),
            trace_ids=ListLineRunParser._parse_string_list(args.trace_ids),
        )


# line run models, for strong type support in Swagger
cumulative_token_count_model = api.model(
    "CumulativeTokenCount",
    {
        CumulativeTokenCountFieldName.COMPLETION: fields.Integer,
        CumulativeTokenCountFieldName.PROMPT: fields.Integer,
        CumulativeTokenCountFieldName.TOTAL: fields.Integer,
    },
)
line_run_model = api.model(
    "LineRun",
    {
        LineRunFieldName.LINE_RUN_ID: fields.String(required=True),
        LineRunFieldName.TRACE_ID: fields.String(required=True),
        LineRunFieldName.ROOT_SPAN_ID: fields.String(required=True),
        LineRunFieldName.INPUTS: fields.Raw(required=True),
        LineRunFieldName.OUTPUTS: fields.Raw(required=True),
        LineRunFieldName.START_TIME: fields.DateTime(required=True, dt_format=PFS_MODEL_DATETIME_FORMAT),
        LineRunFieldName.END_TIME: fields.DateTime(required=True, dt_format=PFS_MODEL_DATETIME_FORMAT),
        LineRunFieldName.STATUS: fields.String(required=True),
        LineRunFieldName.LATENCY: fields.String(required=True),
        LineRunFieldName.NAME: fields.String(required=True),
        LineRunFieldName.KIND: fields.String(required=True),
        LineRunFieldName.CUMULATIVE_TOKEN_COUNT: fields.Nested(cumulative_token_count_model, skip_none=True),
        LineRunFieldName.EVALUATIONS: fields.Raw,
    },
)


@api.route("/list")
class LineRuns(Resource):
    @api.doc(description="List line runs")
    @api.marshal_list_with(line_run_model)
    @api.response(code=200, description="Line runs")
    def get(self):
        client: PFClient = get_client_from_request()
        args = ListLineRunParser.from_request()
        line_runs: typing.List[LineRunEntity] = client._traces.list_line_runs(
            session_id=args.session_id,
            runs=args.runs,
            experiments=args.experiments,
            trace_ids=args.trace_ids,
        )
        # order by start_time desc
        line_runs.sort(key=lambda x: x.start_time, reverse=True)
        return [asdict(line_run) for line_run in line_runs]
