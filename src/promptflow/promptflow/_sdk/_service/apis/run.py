# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json

from flask import jsonify, request
from flask_restx import Namespace, Resource

from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations

api = Namespace("Runs", description="Runs Management")

# Define get connection request parsing
update_run_parser = api.parser()
update_run_parser.add_argument("display_name", type=str, location="args", required=False)
update_run_parser.add_argument("description", type=str, location="args", required=False)
update_run_parser.add_argument("tags", type=str, location="args", required=False)
update_run_parser.add_argument("display_name", type=str, location="args", required=False)

# Response model of connection operation
dict_field = api.schema_model("RunDict", {"additionalProperties": True, "type": "object"})


@api.errorhandler(RunNotFoundError)
def handle_run_not_found_exception(error):
    api.logger.warning(f"Raise RunNotFoundError, {error.message}")
    return {"error_message": error.message}, 404


@api.route("/")
class RunList(Resource):
    @api.marshal_with(dict_field, as_list=True)
    @api.doc(description="List all runs")
    def get(self):
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        all_results = request.args.get("all_results", default=False, type=bool)
        archived_only = request.args.get("archived_only", default=False, type=bool)
        include_archived = request.args.get("include_archived", default=False, type=bool)
        # align with CLI behavior
        if all_results:
            max_results = None
        list_view_type = get_list_view_type(archived_only=archived_only, include_archived=include_archived)

        op = RunOperations()
        runs = op.list(max_results=max_results, list_view_type=list_view_type)
        runs_dict = [run._to_dict() for run in runs]
        return jsonify(runs_dict)


@api.route("/submit")
class RunSubmit(Resource):
    @api.response(code=200, description="Submit run info", model=dict_field)
    @api.doc(description="Submit run")
    def post(self):
        # TODO
        pass


@api.route("/<string:name>")
class Run(Resource):
    @api.response(code=200, description="Update run info", model=dict_field)
    @api.doc(parser=update_run_parser, description="Update run")
    def put(self, name: str):
        args = update_run_parser.parse_args()
        run_op = RunOperations()
        tags = json.loads(args.tags) if args.tags else None
        run = run_op.update(name=name, display_name=args.display_name, description=args.description, tags=tags)
        return jsonify(run._to_dict())

    @api.response(code=200, description="Get run info", model=dict_field)
    @api.doc(description="Get run")
    def get(self, name: str):
        run_op = RunOperations()
        run = run_op.get(name=name)
        return jsonify(run._to_dict())


@api.route("/<string:name>/childRuns")
class FlowChildRuns(Resource):
    @api.marshal_with(dict_field, as_list=True)
    @api.doc(description="Get child runs")
    def get(self, name: str):
        run_op = RunOperations()
        run = run_op.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        detail_dict = local_storage_op.load_detail()
        return jsonify(detail_dict["flow_runs"])


@api.route("/<string:name>/nodeRuns/<string:node_name>")
class FlowNodeRuns(Resource):
    @api.marshal_with(dict_field, as_list=True)
    @api.doc(description="Get node runs info")
    def get(self, name: str, node_name: str):
        run_op = RunOperations()
        run = run_op.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        detail_dict = local_storage_op.load_detail()
        node_runs = [item for item in detail_dict["node_runs"] if item["node"] == node_name]
        return jsonify(node_runs)
