# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import get_client_from_request

api = Namespace("Flows", description="Flows Management")

# Define flow test request parsing
flow_test_parser = api.parser()
flow_test_parser.add_argument("flow", type=str, location="form", required=True)
flow_test_parser.add_argument("node", type=str, location="form", required=False)
flow_test_parser.add_argument("variant", type=str, location="form", required=False)
flow_test_parser.add_argument("detail", type=str, location="form", required=False, default=None)
flow_test_parser.add_argument("experiment", type=str, location="form", required=False)
flow_test_parser.add_argument("inputs", type=dict, location="form", required=False, default={})
flow_test_parser.add_argument("environment_variables", type=dict, location="form", required=False, default={})

# Response model of flow operation
dict_field = api.schema_model("FlowDict", {"additionalProperties": True, "type": "object"})


@api.route("/test")
class FlowTest(Resource):
    @api.response(code=200, description="Flow test", model=dict_field)
    @api.doc(parser=flow_test_parser, description="Flow test")
    def post(self):
        args = flow_test_parser.parse_args()
        if Configuration.get_instance().is_internal_features_enabled() and args.experiment:
            result = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args.environment_variables,
                variant=args.variant,
                node=args.node,
                experiment=args.experiment,
                output_path=args.detail,
            )
        else:
            result = get_client_from_request().flows.test(
                flow=args.flow,
                inputs=args.inputs,
                environment_variables=args.environment_variables,
                variant=args.variant,
                node=args.node,
                allow_generator_output=False,
                stream_output=False,
                dump_test_result=True,
                output_path=args.detail,
            )
        return result
