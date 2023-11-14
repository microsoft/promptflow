# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import yaml
from flask import jsonify, request
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from promptflow._sdk._service.utils import api_wrapper
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._connection import _Connection


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
        client = PFClient()
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        all_results = request.args.get("all_results", default=False, type=bool)

        connections = client.connections.list(max_results=max_results, all_results=all_results)
        connections_dict = [connection._to_dict() for connection in connections]
        return jsonify(connections_dict)


@api.route("/<string:name>")
@api.param("name", "The connection name.")
class Connection(Resource):

    @api.doc(parser=remote_parser, description="Get connection")
    @api_wrapper
    def get(self, name: str):
        client = PFClient()
        # parse query parameters
        with_secrets = request.args.get("with_secrets", default=False, type=bool)
        raise_error = request.args.get("raise_error", default=True, type=bool)

        connection = client.connections.get(name=name, with_secrets=with_secrets, raise_error=raise_error)
        connection_dict = connection._to_dict()
        return jsonify(connection_dict)

    @api.doc(parser=upload_parser, description="Create connection")
    @api_wrapper
    def post(self, name: str):
        client = PFClient()
        args = upload_parser.parse_args()
        params_override = [{k: v} for k, v in upload_parser.argument_class("").source(request).items()]
        connection_data = yaml.safe_load(args['connection_file'].stream)
        params_override.append({"name": name})
        connection = _Connection._load(data=connection_data, params_override=params_override)
        connection = client.connections.create_or_update(connection)
        return jsonify(connection._to_dict())

    @api.doc(parser=remote_parser, description="Update connection")
    @api_wrapper
    def put(self, name: str):
        client = PFClient()
        params_override = [{k: v} for k, v in remote_parser.argument_class("").source(request).items()]
        existing_connection = client.connections.get(name)
        connection = _Connection._load(data=existing_connection._to_dict(), params_override=params_override)
        connection._secrets = existing_connection._secrets
        connection = client.connections.create_or_update(connection)
        return jsonify(connection._to_dict())

    @api.doc(parser=remote_parser, description="Delete connection")
    @api_wrapper
    def delete(self, name: str):
        client = PFClient()
        client.connections.delete(name=name)
