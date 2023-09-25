# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import Blueprint, jsonify, request

from promptflow._sdk._service.utils import api_wrapper
from promptflow._sdk.operations._connection_operations import ConnectionOperations

connection_bp = Blueprint("connection", __name__, url_prefix="/connection/v1.0")


@connection_bp.route("/list", methods=["GET"])
@api_wrapper
def list():
    # parse query parameters
    max_results = request.args.get("max_results", default=50, type=int)
    all_results = request.args.get("all_results", default=False, type=bool)

    op = ConnectionOperations()
    connections = op.list(max_results=max_results, all_results=all_results)
    connections_dict = [connection._to_dict() for connection in connections]
    return jsonify(connections_dict)


@connection_bp.route("/<string:name>", methods=["GET"])
@api_wrapper
def get(name: str):
    # parse query parameters
    with_secrets = request.args.get("with_secrets", default=False, type=bool)
    raise_error = request.args.get("raise_error", default=True, type=bool)

    op = ConnectionOperations()
    connection = op.get(name=name, with_secrets=with_secrets, raise_error=raise_error)
    connection_dict = connection._to_dict()
    return jsonify(connection_dict)
