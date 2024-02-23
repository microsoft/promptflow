# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import shlex
import subprocess
import sys
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from flask import Response, jsonify, make_response, request

from promptflow._cli._pf._init_entry_generators import StreamlitFileReplicator
from promptflow._sdk._constants import FlowRunProperties, get_list_view_type
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._errors import RunNotFoundError, UserErrorException
from promptflow.exceptions import ErrorTarget
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import build_pfs_user_agent, get_client_from_request, make_response_no_content
from promptflow._sdk.entities import Run as RunEntity
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.yaml_utils import dump_yaml
from promptflow.contracts._run_management import RunMetadata

api = Namespace("Flows", description="Flows Management")

# Define flow test request parsing
flow_test_parser = api.parser()
flow_test_parser.add_argument("flow", type=str, location="form", required=True)
flow_test_parser.add_argument("node", type=str, location="form", required=False)
flow_test_parser.add_argument("variant", type=str, location="form", required=False)
flow_test_parser.add_argument("interactive", type=bool, location="form", required=False, default=False)
flow_test_parser.add_argument("multi-modal", type=bool, location="form", required=False, default=False)
flow_test_parser.add_argument("ui", type=bool, location="form", required=False, default=False)
flow_test_parser.add_argument("input", type=str, location="form", required=False)
flow_test_parser.add_argument("detail", type=str, location="form", required=False, default=None)
flow_test_parser.add_argument("experiment", type=str, location="form", required=False)
flow_test_parser.add_argument("skip-open-browser", type=bool, location="form", required=False, default=False)
flow_test_parser.add_argument("inputs", type=dict, location="form", required=False, default={})
flow_test_parser.add_argument("environment-variables", type=dict, location="form", required=False, default={})

# Response model of flow operation
dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})
# list_field = api.schema_model("FlowList", {"type": "array", "items": {"$ref": "#/definitions/Dict"}})


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(parser=flow_test_parser, description="Flow test")
    def post(self):
        args = flow_test_parser.parse_args()
        if Configuration.get_instance().is_internal_features_enabled() and args.experiment:
            if args.variant is not None or args.node is not None:
                error = ValueError("--variant or --node is not supported experiment is specified.")
                raise UserErrorException(
                    target=ErrorTarget.CONTROL_PLANE_SDK,
                    message=str(error),
                    error=error,
                )
            node_results = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args["environment-variables"],
                experiment=args.experiment,
                output_path=args.detail,
            )
            return node_results
        if args["multi-modal"] is True or args.ui is True:
            from promptflow._sdk._load_functions import load_flow

            with tempfile.TemporaryDirectory() as temp_dir:
                flow = load_flow(args.flow)

                script_path = [
                    os.path.join(temp_dir, "main.py"),
                    os.path.join(temp_dir, "utils.py"),
                    os.path.join(temp_dir, "logo.png"),
                ]
                for script in script_path:
                    StreamlitFileReplicator(
                        flow_name=flow.display_name if flow.display_name else flow.name,
                        flow_dag_path=flow.flow_dag_path,
                    ).generate_to_file(script)
                main_script_path = os.path.join(temp_dir, "main.py")
                api.logger.info("Start streamlit with main script generated at: %s", main_script_path)
                get_client_from_request().flows._chat_with_ui(script=main_script_path,
                                                              skip_open_browser=args["skip-open-browser"])
            return
        if args.interactive is True:
            get_client_from_request().flows._chat(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args["environment-variables"],
                variant=args.variant,
            )
            return
        else:
            result = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args["environment-variables"],
                variant=args.variant,
                node=args.node,
                allow_generator_output=False,
                stream_output=False,
                dump_test_result=True,
                output_path=args.detail,
            )
            return result
