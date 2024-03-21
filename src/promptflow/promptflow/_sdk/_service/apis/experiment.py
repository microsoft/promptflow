# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from flask import jsonify, request

from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("Experiments", description="Experiments Management")

# Response model of experiment operation
dict_field = api.schema_model("ExperimentDict", {"additionalProperties": True, "type": "object"})
list_field = api.schema_model("ExperimentList", {"type": "array", "items": {"$ref": "#/definitions/ExperimentDict"}})


@api.route("/")
class ExperimentList(Resource):
    @api.response(code=200, description="Experiments", model=list_field)
    @api.doc(description="List all experiments")
    def get(self):
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        archived_only = request.args.get("archived_only", default=False, type=bool)
        include_archived = request.args.get("include_archived", default=False, type=bool)
        list_view_type = get_list_view_type(archived_only=archived_only, include_archived=include_archived)

        experiments = get_client_from_request()._experiments.list(
            max_results=max_results, list_view_type=list_view_type
        )
        experiments_dict = [experiment._to_dict() for experiment in experiments]
        return jsonify(experiments_dict)
