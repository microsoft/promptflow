# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import asdict, dataclass

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

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


@api.route("/list")
class LineRuns(Resource):
    @api.doc(description="List line runs")
    @api.response(code=200, description="Line runs")
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = ListLineRunParser.from_request()
        line_runs = client._traces.list_line_runs(
            session_id=args.session_id,
        )
        return [asdict(line_run) for line_run in line_runs]
