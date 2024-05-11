# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import traceback
import typing
from dataclasses import dataclass

from flask import current_app
from flask_restx import fields

from promptflow._sdk._constants import PFS_MODEL_DATETIME_FORMAT, CumulativeTokenCountFieldName, LineRunFieldName
from promptflow._sdk._errors import WrongTraceSearchExpressionError
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow._sdk.entities._trace import LineRun as LineRunEntity

api = Namespace("LineRuns", description="Line runs management")


def _parse_string_list_from_api_parser(value: typing.Optional[str]) -> typing.Optional[typing.List[str]]:
    if value is None:
        return None
    return value.split(",")


# parsers for query parameters
# list API
list_line_run_parser = api.parser()
list_line_run_parser.add_argument("session", type=str, required=False)
list_line_run_parser.add_argument("collection", type=str, required=False)
list_line_run_parser.add_argument("run", type=str, required=False)
list_line_run_parser.add_argument("experiment", type=str, required=False)
list_line_run_parser.add_argument("trace_ids", type=str, required=False)
list_line_run_parser.add_argument("line_run_ids", type=str, required=False)


@dataclass
class ListLineRunParser:
    collection: typing.Optional[str] = None
    runs: typing.Optional[typing.List[str]] = None
    experiments: typing.Optional[typing.List[str]] = None
    trace_ids: typing.Optional[typing.List[str]] = None
    session_id: typing.Optional[str] = None
    line_run_ids: typing.Optional[typing.List[str]] = None

    @staticmethod
    def from_request() -> "ListLineRunParser":
        args = list_line_run_parser.parse_args()
        return ListLineRunParser(
            collection=args.collection,
            runs=_parse_string_list_from_api_parser(args.run),
            experiments=_parse_string_list_from_api_parser(args.experiment),
            trace_ids=_parse_string_list_from_api_parser(args.trace_ids),
            session_id=args.session,
            line_run_ids=_parse_string_list_from_api_parser(args.line_run_ids),
        )


# search API
search_line_run_parser = api.parser()
search_line_run_parser.add_argument("expression", type=str, required=True)
search_line_run_parser.add_argument("session", type=str, required=False)
search_line_run_parser.add_argument("collection", type=str, required=False)
search_line_run_parser.add_argument("run", type=str, required=False)


@dataclass
class SearchLineRunParser:
    expression: str
    collection: typing.Optional[str] = None
    runs: typing.Optional[typing.List[str]] = None
    session_id: typing.Optional[str] = None

    @staticmethod
    def from_request() -> "SearchLineRunParser":
        args = search_line_run_parser.parse_args()
        return SearchLineRunParser(
            expression=args.expression,
            collection=args.collection,
            runs=_parse_string_list_from_api_parser(args.run),
            session_id=args.session,
        )


# list collection API
list_collection_parser = api.parser()
list_collection_parser.add_argument("limit", type=int, required=False)


@dataclass
class ListCollectionParser:
    limit: typing.Optional[int] = None

    @staticmethod
    def from_request() -> "ListCollectionParser":
        args = list_collection_parser.parse_args()
        return ListCollectionParser(limit=args.limit)


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
        line_runs: typing.List[LineRunEntity] = client.traces.list_line_runs(
            collection=args.collection,
            runs=args.runs,
            experiments=args.experiments,
            trace_ids=args.trace_ids,
            session_id=args.session_id,
            line_run_ids=args.line_run_ids,
        )
        return [line_run._to_rest_object() for line_run in line_runs]


@api.route("/search")
class LineRunSearch(Resource):
    @api.doc(description="Search line runs")
    @api.marshal_list_with(line_run_model)
    @api.response(code=200, description="Line runs")
    def get(self):
        client: PFClient = get_client_from_request()
        client.traces._logger = current_app.logger
        args = SearchLineRunParser.from_request()
        try:
            line_runs: typing.List[LineRunEntity] = client.traces._search_line_runs(
                expression=args.expression,
                collection=args.collection,
                runs=args.runs,
                session_id=args.session_id,
            )
            return [line_run._to_rest_object() for line_run in line_runs]
        except WrongTraceSearchExpressionError as e:
            current_app.logger.error(traceback.format_exc())
            current_app.logger.error(e)
            api.abort(400, str(e))
        except Exception as e:  # pylint: disable=broad-except
            current_app.logger.error(traceback.format_exc())
            current_app.logger.error(e)
            api.abort(500, str(e))


@api.route("/Collections/list")
class Collections(Resource):
    @api.doc(description="List collections")
    @api.response(code=200, description="Collections")
    def get(self):
        client: PFClient = get_client_from_request()
        args = ListCollectionParser.from_request()
        collections = client.traces._list_collections(limit=args.limit)
        return [collection._to_dict() for collection in collections]
