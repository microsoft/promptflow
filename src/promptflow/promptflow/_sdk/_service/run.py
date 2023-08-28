# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Blueprint, jsonify

from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations

run_bp = Blueprint("run", __name__, url_prefix="/run")


@run_bp.route("/list", methods=["GET"])
def list():
    op = RunOperations()
    runs = op.list()
    runs_dict = [run._to_dict() for run in runs]
    return jsonify(runs_dict)


@run_bp.route("/<string:name>", methods=["GET"])
def get_metadata(name: str):
    op = RunOperations()
    run = op.get(name=name)
    metadata_dict = run._to_dict()
    return jsonify(metadata_dict)


@run_bp.route("/<string:name>/detail", methods=["GET"])
def get_detail(name: str):
    run_op = RunOperations()
    run = run_op.get(name=name)
    local_storage_op = LocalStorageOperations(run=run)
    detail_dict = local_storage_op.load_detail()
    return jsonify(detail_dict)
