# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from flask import jsonify, request
import uuid
import os
from pathlib import Path
import shutil

from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request, decrypt_flow_path
from promptflow._utils.flow_utils import resolve_flow_path
from promptflow.exceptions import UserErrorException

api = Namespace("Experiments", description="Experiments Management")

# Response model of experiment operation
dict_field = api.schema_model("ExperimentDict", {"additionalProperties": True, "type": "object"})
list_field = api.schema_model("ExperimentList", {"type": "array", "items": {"$ref": "#/definitions/ExperimentDict"}})

# Define start experiments request parsing
test_experiment = api.parser()
test_experiment.add_argument("template", type=str, location="json", required=False)
test_experiment.add_argument("inputs", type=list, location="json", required=False)
test_experiment.add_argument("environment_variables", type=str, location="json", required=False)
test_experiment.add_argument("output_path", type=str, location="json", required=False)
test_experiment.add_argument("skip_flow", type=str, location="json", required=False)
test_experiment.add_argument("skip_flow_output", type=dict, location="json", required=False)
test_experiment.add_argument("skip_flow_run_id", type=str, location="json", required=False)


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


@api.route("/test")
class ExperimentTest(Resource):
    @api.doc(description="Test experiment")
    @api.response(code=200, description="Experiment execution details.")
    @api.produces(["text/plain", "application/json"])
    @api.expect(test_experiment)
    def post(self):
        args = test_experiment.parse_args()
        client = get_client_from_request()
        template = args.template
        inputs = args.inputs
        environment_variables = args.environment_variables
        output_path = args.output_path
        skip_flow = args.skip_flow
        if skip_flow:
            skip_flow = decrypt_flow_path(skip_flow)
            flow_path_dir, flow_path_file = resolve_flow_path(skip_flow)
            skip_flow = (flow_path_dir / flow_path_file).as_posix()
        skip_flow_output = args.skip_flow_output
        skip_flow_run_id = args.skip_flow_run_id
        if template:
            api.logger.debug(f"Testing an anonymous experiment {args.template}.")
        else:
            raise UserErrorException("To test an experiment, template must be specified.")

        remove_dir = False

        if output_path is None:
            filename = str(uuid.uuid4())
            if os.path.isdir(template):
                output_path = Path(template) / filename
            else:
                output_path = Path(os.path.dirname(template)) / filename
            os.makedirs(output_path, exist_ok=True)
            remove_dir = True
        output_path = Path(output_path).resolve()

        try:
            result = client._experiments._test_with_ui(
                experiment=template,
                inputs=inputs,
                environment_variables=environment_variables,
                output_path=output_path,
                skip_flow=skip_flow,
                skip_flow_output=skip_flow_output,
                skip_flow_run_id=skip_flow_run_id
            )
        finally:
            if remove_dir:
                shutil.rmtree(output_path)
        return result
