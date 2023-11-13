# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import jsonify, request
from flask_restx import Namespace, Resource, fields, Api

from promptflow._sdk._service.utils import api_wrapper
from promptflow._sdk.operations._connection_operations import ConnectionOperations


api = Namespace("connection", description="Connection Management")

get_connection = api.model(
    "Connection", {"name": fields.String(required=True, description="Connection name")}
)
# list_connection = connection_api.model("ListConnection", )


@api.route("/list")
@api.header(name="X-Remote-User", description="Login user name")
class ConnectionList(Resource):
    @api.doc(description="List all connection")
    @api_wrapper
    def get(self):
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        all_results = request.args.get("all_results", default=False, type=bool)

        op = ConnectionOperations()
        connections = op.list(max_results=max_results, all_results=all_results)
        connections_dict = [connection._to_dict() for connection in connections]
        return jsonify(connections_dict)


@api.route("/<string:name>")
@api.param("name", "The connection name.")
@api.header(name="X-Remote-User", description="Login user name")
class Connection(Resource):

    @api.doc(description="Get connection")
    @api_wrapper
    def get(self, name: str):
        # parse query parameters
        with_secrets = request.args.get("with_secrets", default=False, type=bool)
        raise_error = request.args.get("raise_error", default=True, type=bool)

        op = ConnectionOperations()
        connection = op.get(name=name, with_secrets=with_secrets, raise_error=raise_error)
        connection_dict = connection._to_dict()
        return jsonify(connection_dict)

    def post(self):
        pass

    def delete(self):
        pass
