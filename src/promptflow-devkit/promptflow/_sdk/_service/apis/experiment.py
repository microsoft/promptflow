# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import uuid
from pathlib import Path

from flask import jsonify, request

from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME, get_list_view_type
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request
from promptflow._utils.flow_utils import resolve_flow_path

api = Namespace("Experiments", description="Experiments Management")

# Response model of experiment operation
dict_field = api.schema_model("ExperimentDict", {"additionalProperties": True, "type": "object"})
list_field = api.schema_model("ExperimentList", {"type": "array", "items": {"$ref": "#/definitions/ExperimentDict"}})

base_experiment = api.parser()
base_experiment.add_argument(
    "experiment_template", type=str, location="json", required=True, help="Experiment yaml file path"
)
base_experiment.add_argument(
    "environment_variables", type=str, location="json", required=False, help="Environment variables for experiment"
)
base_experiment.add_argument("output_path", type=str, location="json", required=False)
base_experiment.add_argument("session", type=str, required=False, location="json")

# Define start experiments request parsing
test_experiment = base_experiment.copy()
test_experiment.add_argument(
    "override_flow_path", type=str, location="json", required=False, help="The flow path that need to be override input"
)
test_experiment.add_argument(
    "inputs", type=dict, location="json", required=False, help="Input parameters for experiment"
)
test_experiment.add_argument(
    "main_flow_run_id", type=str, required=False, location="json", help="Designated run id of main flow node"
)
test_experiment.add_argument(
    "main_flow_init",
    type=dict,
    required=False,
    location="json",
    help="Initialization parameters for main flex flow, only supported when flow is callable class.",
)

# Define skip test experiments request parsing
skip_test_experiment = base_experiment.copy()
skip_test_experiment.add_argument("skip_flow", type=str, location="json", required=True)
skip_test_experiment.add_argument("skip_flow_output", type=dict, location="json", required=True)
skip_test_experiment.add_argument("skip_flow_run_id", type=str, location="json", required=True)


def generate_experiment_output_path(experiment_template):
    filename = str(uuid.uuid4())
    if os.path.isdir(experiment_template):
        output_path = Path(experiment_template) / PROMPT_FLOW_DIR_NAME / filename
    else:
        output_path = Path(os.path.dirname(experiment_template)) / PROMPT_FLOW_DIR_NAME / filename
    os.makedirs(output_path, exist_ok=True)
    return output_path


@api.route("/")
class ExperimentList(Resource):
    @api.response(code=200, description="Experiment", model=list_field)
    @api.doc(description="List all experiments")
    def get(self):
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        archived_only = request.args.get("archived_only", default=False, type=bool)
        include_archived = request.args.get("include_archived", default=False, type=bool)
        list_view_type = get_list_view_type(archived_only=archived_only, include_archived=include_archived)

        experiments = get_client_from_request()._experiments.list(
            max_results=max_results, list_view_type=list_view_type
        )
        experiments_dict = [experiment._to_dict() for experiment in experiments]
        return jsonify(experiments_dict)


@api.route("/test_with_flow_override")
class ExperimentTest(Resource):
    @api.doc(description="Test experiment")
    @api.response(code=200, description="Experiment execution details.")
    @api.produces(["text/plain", "application/json"])
    @api.expect(test_experiment)
    def post(self):
        args = test_experiment.parse_args()
        client = get_client_from_request()
        experiment_template = args.experiment_template
        inputs = args.inputs or {}
        override_flow_path = args.override_flow_path
        environment_variables = args.environment_variables
        output_path = args.output_path
        session = args.session
        main_flow_run_id = args.main_flow_run_id
        init = args.main_flow_init or {}

        context = None
        if override_flow_path:
            flow_path_dir, flow_path_file = resolve_flow_path(override_flow_path)
            override_flow_path = (flow_path_dir / flow_path_file).as_posix()
            context = {"inputs": inputs, "node": override_flow_path, "run_id": main_flow_run_id, "init": init}

        if output_path is None:
            output_path = generate_experiment_output_path(experiment_template)
        output_path = Path(output_path).resolve()
        result = client._experiments._test_with_ui(
            experiment=experiment_template,
            output_path=output_path,
            environment_variables=environment_variables,
            session=session,
            context=context,
        )
        # Todo : remove output_path when exit executor which is registered in pfs
        return result


@api.route("/skip_test")
class ExperimentSkipTest(Resource):
    @api.doc(description="Test experiment with skipping node")
    @api.response(code=200, description="Experiment execution details.")
    @api.produces(["text/plain", "application/json"])
    @api.expect(skip_test_experiment)
    def post(self):
        args = skip_test_experiment.parse_args()
        client = get_client_from_request()
        experiment_template = args.experiment_template
        environment_variables = args.environment_variables
        output_path = args.output_path
        session = args.session
        skip_flow = args.skip_flow
        if skip_flow:
            flow_path_dir, flow_path_file = resolve_flow_path(skip_flow)
            skip_flow = (flow_path_dir / flow_path_file).as_posix()
        skip_flow_output = args.skip_flow_output
        skip_flow_run_id = args.skip_flow_run_id
        context = {"node": skip_flow, "outputs": skip_flow_output, "run_id": skip_flow_run_id}

        if output_path is None:
            output_path = generate_experiment_output_path(experiment_template)
        output_path = Path(output_path).resolve()
        result = client._experiments._test_with_ui(
            experiment=experiment_template,
            output_path=output_path,
            environment_variables=environment_variables,
            session=session,
            context=context,
        )
        # Todo : remove output_path when exit executor which is registered in pfs
        return result
