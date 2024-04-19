# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
from pathlib import Path

from flask import jsonify, request

import promptflow._sdk.schemas._connection as connection
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import get_client_from_request, local_user_only, make_response_no_content
from promptflow._sdk.entities._connection import _Connection

api = Namespace("Connections", description="Connections Management")


# azure connection
def validate_working_directory(value):
    if value is None:
        return
    if not isinstance(value, str):
        value = str(value)

    if not Path(value).is_dir():
        raise ValueError("Invalid working directory.")
    return value


working_directory_parser = api.parser()
working_directory_parser.add_argument(
    "working_directory", type=validate_working_directory, location="args", required=False
)

# Response model of list connections
list_connection_field = api.model(
    "Connection",
    {
        "name": fields.String,
        "type": fields.String,
        "module": fields.String,
        "expiry_time": fields.String,
        "created_date": fields.String,
        "last_modified_date": fields.String,
    },
)
# Response model of connection operation
dict_field = api.schema_model("ConnectionDict", {"additionalProperties": True, "type": "object"})
# Response model of connection spec
connection_config_spec_model = api.model(
    "ConnectionConfigSpec",
    {
        "name": fields.String,
        "optional": fields.Boolean,
        "default": fields.String,
    },
)
connection_spec_model = api.model(
    "ConnectionSpec",
    {
        "connection_type": fields.String,
        "config_spec": fields.List(fields.Nested(connection_config_spec_model)),
    },
)


def _get_connection_operation(working_directory=None):
    connection_provider = Configuration().get_connection_provider(path=working_directory)
    # get_connection_operation is a shared function, so we build user agent based on request first and
    # then pass it to the function
    connection_operation = get_client_from_request(connection_provider=connection_provider).connections
    return connection_operation


@api.route("/")
class ConnectionList(Resource):
    @api.doc(parser=working_directory_parser, description="List all connection")
    @api.marshal_with(list_connection_field, skip_none=True, as_list=True)
    def get(self):
        args = working_directory_parser.parse_args()
        connection_op = _get_connection_operation(args.working_directory)
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        all_results = request.args.get("all_results", default=False, type=bool)

        connections = connection_op.list(max_results=max_results, all_results=all_results)
        connections_dict = [connection._to_dict() for connection in connections]
        return connections_dict


@api.route("/<string:name>")
@api.param("name", "The connection name.")
class Connection(Resource):
    @api.doc(parser=working_directory_parser, description="Get connection")
    @api.response(code=200, description="Connection details", model=dict_field)
    def get(self, name: str):
        args = working_directory_parser.parse_args()
        connection_op = _get_connection_operation(args.working_directory)
        connection = connection_op.get(name=name, raise_error=True)
        connection_dict = connection._to_dict()
        return jsonify(connection_dict)

    @api.doc(body=dict_field, description="Create connection")
    @api.response(code=200, description="Connection details", model=dict_field)
    def post(self, name: str):
        connection_op = _get_connection_operation()
        connection_data = request.get_json(force=True)
        connection_data["name"] = name
        connection = _Connection._load(data=connection_data)
        connection = connection_op.create_or_update(connection)
        return jsonify(connection._to_dict())

    @api.doc(body=dict_field, description="Update connection")
    @api.response(code=200, description="Connection details", model=dict_field)
    def put(self, name: str):
        connection_op = _get_connection_operation()
        connection_dict = request.get_json(force=True)
        params_override = [{k: v} for k, v in connection_dict.items()]
        # TODO: check if we need to record registry for this private operation
        existing_connection = connection_op._get(name)
        connection = _Connection._load(data=existing_connection._to_dict(), params_override=params_override)
        connection._secrets = existing_connection._secrets
        connection = connection_op.create_or_update(connection)
        return jsonify(connection._to_dict())

    @api.doc(description="Delete connection")
    @api.response(code=204, description="Delete connection", model=dict_field)
    def delete(self, name: str):
        connection_op = _get_connection_operation()
        connection_op.delete(name=name)
        return make_response_no_content()


@api.route("/<string:name>/listsecrets")
class ConnectionWithSecret(Resource):
    @api.doc(parser=working_directory_parser, description="Get connection with secret")
    @api.response(code=200, description="Connection details with secret", model=dict_field)
    @local_user_only
    @api.response(
        code=403, description="This service is available for local user only, please specify X-Remote-User in headers."
    )
    def get(self, name: str):
        args = working_directory_parser.parse_args()
        connection_op = _get_connection_operation(args.working_directory)
        connection = connection_op.get(name=name, with_secrets=True, raise_error=True)
        connection_dict = connection._to_dict()
        return jsonify(connection_dict)


@api.route("/specs")
class ConnectionSpecs(Resource):
    @api.doc(description="List connection spec")
    @api.response(code=200, description="List connection spec", skip_none=True, model=connection_spec_model)
    def get(self):
        hide_connection_fields = ["module"]
        connection_specs = []
        for name, obj in inspect.getmembers(connection):
            if (
                inspect.isclass(obj)
                and issubclass(obj, connection.ConnectionSchema)
                and not isinstance(obj, connection.ConnectionSchema)
            ):
                config_specs = []
                for field_name, field in obj._declared_fields.items():
                    if not field.dump_only and field_name not in hide_connection_fields:
                        configs = {"name": field_name, "optional": field.allow_none}
                        if field.default:
                            configs["default"] = field.default
                        if field_name == "type":
                            configs["default"] = field.allowed_values[0]
                        config_specs.append(configs)
                connection_spec = {
                    "connection_type": name.replace("Schema", ""),
                    "config_specs": config_specs,
                }
                connection_specs.append(connection_spec)
        return jsonify(connection_specs)
