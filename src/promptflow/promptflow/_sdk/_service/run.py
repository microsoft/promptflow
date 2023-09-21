# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._service.utils import api_wrapper
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow.contracts._run_management import RunMetadata

run_bp = Blueprint("run", __name__, url_prefix="/run/v1.0")


@run_bp.route("/list", methods=["GET"])
@api_wrapper
def list():
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


@run_bp.route("/<string:name>", methods=["GET"])
@api_wrapper
def get(name: str):
    op = RunOperations()
    run = op.get(name=name)
    run_dict = run._to_dict()
    return jsonify(run_dict)


@run_bp.route("/<string:name>/metadata", methods=["GET"])
@api_wrapper
def get_metadata(name: str):
    run_op = RunOperations()
    run = run_op.get(name=name)
    local_storage_op = LocalStorageOperations(run=run)
    metadata = RunMetadata(
        name=run.name,
        display_name=run.display_name,
        create_time=run.created_on,
        tags=run.tags,
        lineage=run.run,
        metrics=local_storage_op.load_metrics(),
        dag=local_storage_op.load_dag_as_string(),
        flow_tools_json=local_storage_op.load_flow_tools_json(),
    )
    return jsonify(asdict(metadata))


@run_bp.route("/<string:name>/detail", methods=["GET"])
@api_wrapper
def get_detail(name: str):
    run_op = RunOperations()
    run = run_op.get(name=name)
    local_storage_op = LocalStorageOperations(run=run)
    detail_dict = local_storage_op.load_detail()
    return jsonify(detail_dict)
