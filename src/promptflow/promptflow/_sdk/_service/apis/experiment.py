# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
import json
from flask import jsonify, stream_with_context, Response
from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._load_functions import _load_experiment_template
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow.exceptions import UserErrorException

api = Namespace("Experiments", description="Experiments Management")
dict_field = api.schema_model("ExperimentDict", {"additionalProperties": True, "type": "object"})
list_field = api.schema_model("ExperimentList", {"type": "array", "items": {"$ref": "#/definitions/ExperimentDict"}})

# Define create or update experiment request parsing
create_or_update_experiment = api.parser()
create_or_update_experiment.add_argument("template", type=str, location="json", required=True)

# Define list experiments request parsing
list_experiment = api.parser()
list_experiment.add_argument("max_results", type=int, default=None, location="query", required=False)
list_experiment.add_argument("all_results", type=bool, default=False, location="query", required=False)
list_experiment.add_argument("archived_only", type=bool, default=False, location="query", required=False)
list_experiment.add_argument("include_archived", type=bool, default=False, location="query", required=False)

# Define start experiments request parsing
stop_experiment = api.parser()
stop_experiment.add_argument("name", type=str, location="json", required=False)
stop_experiment.add_argument("template", type=str, location="json", required=False)

# Define start experiments request parsing
start_experiment = api.parser()
start_experiment.add_argument("name", type=str, location="json", required=False)
start_experiment.add_argument("template", type=str, location="json", required=False)
start_experiment.add_argument("stream", type=bool, default=False, location="json", required=False)
start_experiment.add_argument("from_nodes", type=list, location="json", required=False)
start_experiment.add_argument("nodes", type=list, location="json", required=False)
start_experiment.add_argument("inputs", type=list, location="json", required=False)
start_experiment.add_argument("executable_path", type=str, location="json", required=False)


@api.route("/")
class ExperimentList(Resource):
    @api.response(code=200, description="Experiments", model=list_field)
    @api.doc(description="List all experiments")
    @api.expect(list_experiment)
    def get(self):
        args = list_experiment.parse_args()

        list_view_type = get_list_view_type(archived_only=args.archived_only, include_archived=args.include_archived)
        results = get_client_from_request()._experiments.list(args.max_results, list_view_type=list_view_type)
        return jsonify([result._to_dict() for result in results])


@api.route("/<string:name>")
class Experiment(Resource):
    @api.doc(description="Get experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def get(self, name: str):
        result = get_client_from_request()._experiments.get(name)
        return jsonify(result._to_dict())

    @api.doc(description="Create experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    @api.expect(create_or_update_experiment)
    def post(self, name: str):
        from promptflow._sdk.entities._experiment import Experiment as ExperimentEntry

        args = create_or_update_experiment.parse_args()
        if not Path(args.template).is_absolute():
            raise UserErrorException("Please provide the absolute path of template.")
        if not Path(args.template).exists():
            raise UserErrorException(f"Template path {args.template} doesn't exist.")
        api.logger.debug("Loading experiment template from %s", args.template)
        template = _load_experiment_template(source=args.template)
        experiment = ExperimentEntry.from_template(template, name=name)
        api.logger.debug("Creating experiment %s", experiment.name)
        client = get_client_from_request()
        exp = client._experiments.create_or_update(experiment)
        return jsonify(exp._to_dict())

    @api.doc(description="Update experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def put(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Update experiment has not been implemented.")

    @api.doc(description="Delete experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def delete(self, name: str):
        # TODO update experiment
        raise NotImplementedError("Delete experiment has not been implemented.")


@api.route("/start")
class ExperimentStart(Resource):
    @api.doc(description="Start experiment")
    @api.response(code=200, description="Experiment execution details.")
    @api.produces(['application/octet-stream', "application/json"])
    @api.expect(start_experiment)
    def post(self):
        def stream_experiment_run(experiment_obj):
            from promptflow._sdk._submitter.utils import _get_experiment_log_path
            from promptflow._sdk._submitter.experiment_orchestrator import ExperimentOrchestrator
            from promptflow._sdk._constants import ExperimentStatus
            import time

            yield json.dumps(experiment_obj._to_dict(), indent=4) + "\r\n"
            experiment_log_path = _get_experiment_log_path(experiment_obj._output_dir)
            with open(experiment_log_path, "r") as f:
                while ExperimentOrchestrator.get_status(experiment_obj.name) != ExperimentStatus.TERMINATED:
                    yield f.readline()

        args = start_experiment.parse_args()
        client = get_client_from_request()
        inputs = args.inputs
        if args.name:
            api.logger.debug(f"Starting a named experiment {args.name}.")
            experiment = client._experiments.get(args.name)
        elif args.template:
            from promptflow._sdk._load_functions import _load_experiment

            api.logger.debug(f"Starting an anonymous experiment {args.template}.")
            experiment = _load_experiment(source=args.template)
        else:
            raise UserErrorException("To start an experiment, one of [name, template] must be specified.")
        result = client._experiments.start(experiment=experiment, inputs=inputs, nodes=args.nodes,
                                           from_nodes=args.from_nodes, executable_path=args.executable_path)
        if args.stream:
            return Response(stream_experiment_run(result), content_type='application/octet-stream')
        else:
            return jsonify(result._to_dict())


@api.route("/stop")
class ExperimentStop(Resource):
    @api.doc(body=dict_field, description="Stop experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self):
        args = stop_experiment.parse_args()
        if args.name:
            api.logger.debug(f"Stop a named experiment {args.name}.")
            experiment_name = args.name
        elif args.file:
            from promptflow._sdk._load_functions import _load_experiment

            api.logger.debug(f"Stop an anonymous experiment {args.file}.")
            experiment = _load_experiment(source=args.file)
            experiment_name = experiment.name
        else:
            raise UserErrorException("To stop an experiment, one of [name, template] must be specified.")
        result = get_client_from_request()._experiments.stop(name=experiment_name)
        return jsonify(result._to_dict())


@api.route("/<string:name>/test")
class ExperimentTest(Resource):
    @api.doc(body=dict_field, description="Test experiment")
    @api.response(code=200, description="Experiment details", model=dict_field)
    def post(self, name: str):
        raise NotImplementedError("Test experiment has not been implemented.")
