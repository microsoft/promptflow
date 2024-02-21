# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import hashlib
import typing
from dataclasses import asdict, dataclass

from flask_restx import fields

from promptflow._sdk._constants import PFS_MODEL_DATETIME_FORMAT, CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

HASH_HEADER_IN_LINE_RUNS_LIST = "X-Line-Runs-List-Hash"

api = Namespace("LineRuns", description="Line runs management")

# parsers for query parameters
list_line_run_parser = api.parser()
list_line_run_parser.add_argument("session", type=str, required=False)


# use @dataclass for strong type
@dataclass
class ListLineRunParser:
    session_id: typing.Optional[str] = None

    @staticmethod
    def from_request() -> "ListLineRunParser":
        args = list_line_run_parser.parse_args()
        return ListLineRunParser(
            session_id=args.session,
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
evaluation_line_run_model = api.model(
    "EvaluationLineRun",
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
        LineRunFieldName.DISPLAY_NAME: fields.String(required=True),
        LineRunFieldName.KIND: fields.String(required=True),
        LineRunFieldName.CUMULATIVE_TOKEN_COUNT: fields.Nested(cumulative_token_count_model, skip_none=True),
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
        LineRunFieldName.DISPLAY_NAME: fields.String(required=True),
        LineRunFieldName.KIND: fields.String(required=True),
        LineRunFieldName.CUMULATIVE_TOKEN_COUNT: fields.Nested(cumulative_token_count_model, skip_none=True),
        LineRunFieldName.EVALUATIONS: fields.List(fields.Nested(evaluation_line_run_model, skip_none=True)),
    },
)


@api.route("/list")
class LineRuns(Resource):
    @api.doc(description="List line runs")
    @api.marshal_list_with(line_run_model)
    @api.response(code=200, description="Line runs")
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = ListLineRunParser.from_request()
        line_runs = client._traces.list_line_runs(
            session_id=args.session_id,
        )

        line_runs_id_list, line_runs_dict = [], []
        for line_run in line_runs:
            line_runs_id_list.append(line_run.line_run_id)
            line_runs_dict.append(asdict(line_run))

        # create a hash of the sorted list of line run ids
        # and add it to the response header
        # so that UX can use it to determine if the line runs have changed
        line_runs_id_list.sort()
        line_runs_hash = hashlib.sha256(",".join(line_runs_id_list).encode()).hexdigest()

        return line_runs_dict, 200, {HASH_HEADER_IN_LINE_RUNS_LIST: line_runs_hash}
