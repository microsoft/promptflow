# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import shutil
import uuid
from pathlib import Path
from flask_restx import reqparse

from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import decrypt_flow_path, get_client_from_request


api = Namespace("Flows", description="Flows Management")


dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})

flow_test_model = api.model(
    "FlowTest",
    {
        "node": fields.String(
            required=False, description="If specified it will only test this node, else it will " "test the flow."
        ),
        "variant": fields.String(
            required=False,
            description="Node & variant name in format of ${"
            "node_name.variant_name}, will use default variant if "
            "not specified.",
        ),
        "output_path": fields.String(required=False, description="Output path of flow"),
        "experiment": fields.String(required=False, description="Path of experiment template"),
        "inputs": fields.Nested(dict_field, required=False),
        "environment_variables": fields.Nested(dict_field, required=False),
    },
)

flow_path_parser = reqparse.RequestParser()
flow_path_parser.add_argument("flow", type=str, required=True, location="args", help="Path to flow directory.")


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(description="Flow test")
    @api.expect(flow_test_model)
    def post(self):
        args = flow_path_parser.parse_args()
        flow = args.flow
        flow = decrypt_flow_path(flow)
        inputs = api.payload.get("inputs", None)
        environment_variables = api.payload.get("environment_variables", None)
        variant = api.payload.get("variant", None)
        node = api.payload.get("node", None)
        experiment = api.payload.get("experiment", None)
        output_path = api.payload.get("output_path", None)
        remove_dir = False

        if output_path is None:
            filename = str(uuid.uuid4())
            if os.path.isdir(flow):
                output_path = Path(flow) / PROMPT_FLOW_DIR_NAME / filename
            else:
                output_path = Path(os.path.dirname(flow)) / PROMPT_FLOW_DIR_NAME / filename
            os.makedirs(output_path, exist_ok=True)
            remove_dir = True
        output_path = Path(output_path).resolve()
        try:
            result = get_client_from_request().flows._test_with_ui(
                flow=flow,
                inputs=inputs,
                environment_variables=environment_variables,
                variant=variant,
                node=node,
                experiment=experiment,
                output_path=output_path,
            )
        finally:
            if remove_dir:
                shutil.rmtree(output_path)
        return result
