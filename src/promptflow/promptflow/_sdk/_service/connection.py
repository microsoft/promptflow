# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from flask import jsonify, request
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from promptflow._sdk._service.utils import api_wrapper
from promptflow._sdk.operations._connection_operations import ConnectionOperations


api = Namespace("Connections", description="Connections Management")

upload_parser = api.parser()
upload_parser.add_argument('connection_file', location='files', type=FileStorage, required=True)
upload_parser.add_argument('X-Remote-User', location='headers', required=True)


remote_parser = api.parser()
remote_parser.add_argument('X-Remote-User', location='headers', required=True)


@api.route("/")
class ConnectionList(Resource):
    @api.doc(parser=remote_parser, description="List all connection")
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
class Connection(Resource):

    @api.doc(parser=remote_parser, description="Get connection")
    @api_wrapper
    def get(self, name: str):
        # parse query parameters
        with_secrets = request.args.get("with_secrets", default=False, type=bool)
        raise_error = request.args.get("raise_error", default=True, type=bool)

        op = ConnectionOperations()
        connection = op.get(name=name, with_secrets=with_secrets, raise_error=raise_error)
        connection_dict = connection._to_dict()
        return jsonify(connection_dict)

    @api.doc(parser=upload_parser, description="Create connection")
    @api_wrapper
    def post(self, name: str):
        pass

    @api.doc(parser=remote_parser, description="Update connection")
    @api_wrapper
    def put(self, name: str):
        pass

    @api.doc(parser=remote_parser, description="Delete connection")
    @api_wrapper
    def delete(self, name: str):
        pass
