# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect
from pathlib import Path
import json
from flask import jsonify, request
from promptflow._sdk._constants import get_list_view_type
import promptflow._sdk.schemas._connection as connection
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import get_client_from_request, local_user_only, make_response_no_content
from promptflow._sdk.entities._connection import _Connection
from promptflow._sdk.entities._experiment import Experiment, ExperimentTemplate
from promptflow.exceptions import UserErrorException
from promptflow._sdk._load_functions import load_common

api = Namespace("Experiments", description="Experiments Management")
dict_field = api.schema_model("ExperimentDict", {"additionalProperties": True, "type": "object"})

# Define create or update experiment request parsing
create_or_update_experiment = api.parser()
create_or_update_experiment.add_argument("template", type=str, location="form", required=True)

# Define list experiments request parsing
list_experiment = api.parser()
list_experiment.add_argument("max_results", type=int, location="form", required=False)
list_experiment.add_argument("all_results", type=bool, default=True, location="form", required=False)
list_experiment.add_argument("archived_only", type=bool, default=True, location="form", required=False)
list_experiment.add_argument("include_archived", type=int, default=True, location="form", required=False)

# Define start experiments request parsing
start_experiment = api.parser()
start_experiment.add_argument("from_nodes", type=str, action="append", required=False)
start_experiment.add_argument("nodes", type=str, action="append", required=False)
start_experiment.add_argument("executable_path", type=str, required=False)


@api.route("/")
class ExperimentList(Resource):
    @api.doc(parser=working_directory_parser, description="List all connection")
    @api.marshal_with(list_connection_field, skip_none=True, as_list=True)
    @local_user_only
    @api.response(
        code=403, description="This service is available for local user only, please specify X-Remote-User in headers."
    )
    def get(self):
        args = list_experiment.parse_args()

        list_view_type = get_list_view_type(archived_only=args.archived_only, include_archived=args.include_archived)
        results = get_client_from_request()._experiments.list(args.max_results, list_view_type=list_view_type)
        return jsonify([result._to_dict() for result in results])


@api.route("/<string:name>")
class Experiment(Resource):
    @api.response(code=200, description="Experiment details", model=dict_field)
    def get(self, name: str):
        result = get_client_from_request()._experiments.get(name)
        return jsonify(result._to_dict())

    @api.doc(body=dict_field, description="Create experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self, name: str):
        args = create_or_update_experiment.parse_args()
        if not Path(args.template).is_absolute():
            raise UserErrorException("Please provide the absolute path of template.")
        if not Path(args.template).exists():
            raise UserErrorException(f"Template path {args.template} doesn't exist.")
        api.logger.debug("Loading experiment template from %s", args.template)
        template = load_common(ExperimentTemplate, source=args.template)
        api.logger.debug("Creating experiment from template %s", template.name)
        experiment = Experiment.from_template(template, name=name)
        api.logger.debug("Creating experiment %s", experiment.name)
        client = get_client_from_request()
        exp = client._experiments.create_or_update(experiment)
        return jsonify(exp._to_dict())

    @api.doc(body=dict_field, description="Update experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def put(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Update experiment has not been implemented.")

    @api.doc(body=dict_field, description="Delete experiment")
    def delete(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Delete experiment has not been implemented.")


@api.route("/<string:name>/start")
class ExperimentStart(Resource):
    @api.doc(body=dict_field, description="Start experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self, name: str):
        args = start_experiment.parse_args()
        result = get_client_from_request()._experiments.start(
            name=name, nodes=args.nodes, from_nodes=args.from_nodes, executable_path=args.executable_path)
        return jsonify(result._to_dict())


@api.route("/<string:name>/stop")
class ExperimentStop(Resource):
    @api.doc(body=dict_field, description="Stop experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def get(self, name: str):
        result = get_client_from_request()._experiments.stop(name=name)
        return jsonify(result._to_dict())


@api.route("/<string:name>/test")
class ExperimentTest(Resource):
    @api.doc(body=dict_field, description="Test experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Test experiment has not been implemented.")


@api.route("/<string:name>/clone")
class ExperimentStop(Resource):
    @api.doc(body=dict_field, description="Clone experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Clone experiment has not been implemented.")
