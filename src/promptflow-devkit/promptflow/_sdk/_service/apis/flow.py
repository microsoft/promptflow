# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import uuid
from pathlib import Path

from flask import jsonify, request

from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import decrypt_flow_path, get_client_from_request
from promptflow._utils.flow_utils import is_prompty_flow, resolve_flow_path
from promptflow.client import load_flow

api = Namespace("Flows", description="Flows Management")


dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})


flow_path_parser = api.parser()
flow_path_parser.add_argument("flow", type=str, required=True, location="args", help="Path to flow directory.")
flow_path_parser.add_argument(
    "node",
    type=str,
    required=False,
    location="json",
    help="If specified it will only test this node, else it will test the flow.",
)
flow_path_parser.add_argument(
    "variant",
    type=str,
    required=False,
    location="json",
    help="Node & variant name in format of ${node_name.variant_name}, will use default variant if not specified.",
)
flow_path_parser.add_argument("output_path", type=str, required=False, location="json", help="Output path of flow.")
flow_path_parser.add_argument(
    "experiment", type=str, required=False, location="json", help="Path of experiment template."
)
flow_path_parser.add_argument("inputs", type=dict, required=False, location="json")
flow_path_parser.add_argument("environment_variables", type=dict, required=False, location="json")
flow_path_parser.add_argument("session", type=str, required=False, location="json")
flow_path_parser.add_argument(
    "init",
    type=dict,
    required=False,
    location="json",
    help="Initialization parameters for flex flow, only supported when flow is callable class.",
)
flow_path_parser.add_argument("run_id", type=str, required=False, location="json", help="Designated run id of flow")

flow_infer_signature_parser = api.parser()
flow_infer_signature_parser.add_argument(
    "source", type=str, required=True, location="args", help="Path to flow or prompty."
)


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(description="Flow test")
    @api.expect(flow_path_parser)
    def post(self):
        args = flow_path_parser.parse_args()
        flow = decrypt_flow_path(args.flow)
        is_prompty = is_prompty_flow(flow)
        if is_prompty:
            flow = Path(flow).absolute()
        else:
            flow, _ = resolve_flow_path(flow)
        inputs = args.inputs
        environment_variables = args.environment_variables
        variant = args.variant
        node = args.node
        experiment = args.experiment
        output_path = args.output_path
        session = args.session
        init = args.init
        run_id = args.run_id

        if output_path is None:
            filename = str(uuid.uuid4())
            if is_prompty:
                output_path = flow.parent / PROMPT_FLOW_DIR_NAME / flow.stem / filename
            else:
                output_path = flow / PROMPT_FLOW_DIR_NAME / filename
            os.makedirs(output_path, exist_ok=True)
        output_path = Path(output_path).resolve()
        result = get_client_from_request().flows._test_with_ui(
            flow=flow,
            output_path=output_path,
            inputs=inputs,
            environment_variables=environment_variables,
            variant=variant,
            node=node,
            experiment=experiment,
            session=session,
            init=init,
            run_id=run_id,
            allow_generator_output=False,
            stream_output=False,
            dump_test_result=True,
        )
        # Todo : remove output_path when exit executor which is registered in pfs
        return result


@api.route("/infer_signature")
class FlowInferSignature(Resource):
    @api.response(code=200, description="Flow infer signature", model=dict_field)
    @api.doc(description="Flow infer signature")
    @api.expect(flow_infer_signature_parser)
    def post(self):
        args = flow_infer_signature_parser.parse_args()
        flow_path = decrypt_flow_path(args.source)
        flow = load_flow(source=flow_path)
        include_primitive_output = request.args.get("include_primitive_output", default=False, type=bool)

        infer_signature = get_client_from_request().flows._infer_signature(
            entry=flow, include_primitive_output=include_primitive_output
        )
        return jsonify(infer_signature)
