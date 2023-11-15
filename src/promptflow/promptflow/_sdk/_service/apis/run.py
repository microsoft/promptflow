# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import asdict
from flask_restx import Namespace, Resource, fields, Api

from flask import jsonify, request

from promptflow._sdk._constants import FlowRunProperties, get_list_view_type
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow.contracts._run_management import RunMetadata
from promptflow._sdk._errors import ConnectionNotFoundError, RunNotFoundError

api = Namespace("run", description="Run Management")


@api.errorhandler(RunNotFoundError)
def handle_run_not_found_exception(error):
    return {"error_message": error.message}, 400


@api.route("/list")
class RunList(Resource):

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


@api.route("/<string:name>")
class Run(Resource):

    def get(self, name: str):
        op = RunOperations()
        run = op.get(name=name)
        run_dict = run._to_dict()
        return jsonify(run_dict)


@api.route("/metadata/<string:name>")
class MetaData(Resource):

    def get(self, name: str):
        run_op = RunOperations()
        run = run_op.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        metadata = RunMetadata(
            name=run.name,
            display_name=run.display_name,
            create_time=run.created_on,
            flow_path=run.properties[FlowRunProperties.FLOW_PATH],
            output_path=run.properties[FlowRunProperties.OUTPUT_PATH],
            tags=run.tags,
            lineage=run.run,
            metrics=local_storage_op.load_metrics(),
            dag=local_storage_op.load_dag_as_string(),
            flow_tools_json=local_storage_op.load_flow_tools_json(),
        )
        return jsonify(asdict(metadata))


@api.route("/detail/<string:name>")
class Detail(Resource):

    def get(self, name: str):
        run_op = RunOperations()
        run = run_op.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        detail_dict = local_storage_op.load_detail()
        return jsonify(detail_dict)
