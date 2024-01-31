# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import typing
from dataclasses import dataclass

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.models.span import models, span_model
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("spans", description="Span Management")

# parsers for query parameters
list_span_parser = api.parser()
list_span_parser.add_argument("session_id", type=str, required=False)
list_span_parser.add_argument("parent_span_id", type=str, required=False)


# use @dataclass for strong type
@dataclass
class ListSpanParser:
    session_id: typing.Optional[str] = None
    parent_span_id: typing.Optional[str] = None

    @staticmethod
    def from_request() -> "ListSpanParser":
        args = list_span_parser.parse_args()
        return ListSpanParser(
            session_id=args.session_id,
            parent_span_id=args.parent_span_id,
        )


# span models, for strong type support in Swagger
for name, model in models:
    api.model(name, model)


@api.route("/list")
class Spans(Resource):
    @api.doc(description="List spans")
    @api.marshal_list_with(span_model)
    @api.response(code=200, description="Spans")
    def get(self):
        from promptflow import PFClient

        client: PFClient = get_client_from_request()
        args = ListSpanParser.from_request()
        spans = client._traces.list_spans(
            session_id=args.session_id,
            parent_span_id=args.parent_span_id,
        )
        return [span._content for span in spans]
