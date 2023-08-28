# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import asdict

from flask import Blueprint, jsonify

from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow.contracts._run_management import RunMetadata

run_bp = Blueprint("run", __name__, url_prefix="/run")


@run_bp.route("/list", methods=["GET"])
def list():
    op = RunOperations()
    runs = op.list()
    runs_dict = [run._to_dict() for run in runs]
    return jsonify(runs_dict)


@run_bp.route("/<string:name>", methods=["GET"])
def get(name: str):
    op = RunOperations()
    run = op.get(name=name)
    run_dict = run._to_dict()
    return jsonify(run_dict)


@run_bp.route("/<string:name>/metadata", methods=["GET"])
def get_metadata(name: str):
    run_op = RunOperations()
    run = run_op.get(name=name)
    local_storage_op = LocalStorageOperations(run=run)
    metadata = RunMetadata(
        name=run.name,
        display_name=run.display_name,
        tags=run.tags,
        lineage=run.run,
        metrics=local_storage_op.load_metrics(),
        dag=local_storage_op.load_dag_as_string(),
        # TODO(zhengfei): investigate why this will lead to API break
        # flow_tools_json=local_storage_op.load_flow_tools_json(),
        flow_tools_json=None,
    )
    return jsonify(asdict(metadata))


@run_bp.route("/<string:name>/detail", methods=["GET"])
def get_detail(name: str):
    run_op = RunOperations()
    run = run_op.get(name=name)
    local_storage_op = LocalStorageOperations(run=run)
    detail_dict = local_storage_op.load_detail()
    return jsonify(detail_dict)
