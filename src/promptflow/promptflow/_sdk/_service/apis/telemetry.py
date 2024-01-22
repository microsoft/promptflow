# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from flask import jsonify, make_response

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import build_pfs_user_agent, local_user_only
from promptflow._sdk._telemetry import ActivityCompletionStatus, ActivityType
from promptflow._utils.utils import camel_to_snake
from promptflow.exceptions import UserErrorException

api = Namespace("Telemetries", description="Telemetry Management")

dict_field = api.schema_model("RunDict", {"additionalProperties": True, "type": "object"})


class EventType:
    START = "Start"
    END = "End"


class AllowedActivityName:
    FLOW_TEST = "pf.flow.test"
    FLOW_NODE_TEST = "pf.flow.node_test"
    GENERATE_TOOL_META = "pf.flow._generate_tools_meta"


REQUEST_ID_KEY = "x-ms-promptflow-request-id"


def _dict_camel_to_snake(data):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[camel_to_snake(key)] = _dict_camel_to_snake(value)
        return result
    else:
        return data


def parse_activity_info(metadata, first_call, user_agent, request_id):
    request_id = request_id

    return {
        "request_id": request_id,
        "first_call": first_call,
        "user_agent": user_agent,
        **_dict_camel_to_snake(metadata),
    }


def validate_metadata(value: dict) -> dict:
    allowed_activity_names = [
        AllowedActivityName.FLOW_TEST,
        AllowedActivityName.FLOW_NODE_TEST,
        AllowedActivityName.GENERATE_TOOL_META,
    ]
    if value.get("activityName", None) not in allowed_activity_names:
        raise UserErrorException(f"metadata.activityName must be one of {', '.join(allowed_activity_names)}.")

    allowed_activity_types = [
        ActivityType.INTERNALCALL,
        ActivityType.PUBLICAPI,
    ]
    if value.get("activityType") not in allowed_activity_types:
        raise UserErrorException(f"metadata.activityType must be one of {', '.join(allowed_activity_types)}")
    return value


def validate_metadata_based_on_event_type(metadata: dict, event_type: str):
    if event_type == EventType.END:
        if not all(
            key in metadata
            for key in (
                "completionStatus",  # End event should have completionStatus
                "durationMs",  # End event should have durationMs
            )
        ):
            missing_fields = {"completionStatus", "durationMs"} - set(metadata.keys())
            raise UserErrorException(f"Missing required fields in telemetry metadata: {', '.join(missing_fields)}")

        if metadata.get("completionStatus") not in [
            ActivityCompletionStatus.FAILURE,
            ActivityCompletionStatus.SUCCESS,
        ]:
            raise UserErrorException(f"Invalid completionStatus: {metadata.get('completionStatus')}")

        if metadata.get("completionStatus") == ActivityCompletionStatus.FAILURE:
            if not all(
                key in metadata
                for key in (
                    "errorCategory",  # Failure event should have errorCategory
                    "errorType",  # Failure event should have errorType
                    "errorTarget",  # Failure event should have errorTarget
                    "errorMessage",  # Failure event should have errorMessage
                )
            ):
                missing_fields = {"errorCategory", "errorType", "errorTarget", "errorMessage"} - set(metadata.keys())
                raise UserErrorException(f"Missing required fields in telemetry payload: {', '.join(missing_fields)}")


def validate_event_type(value) -> str:
    if value not in (EventType.START, EventType.END):
        raise ValueError(f"Event type must be one of {EventType.START} and {EventType.END}.")
    return value


telemetry_parser = api.parser()
telemetry_parser.add_argument(
    REQUEST_ID_KEY,
    type=str,
    location="headers",
    required=True,
    help="The request id of the telemetry; all telemetries during one public operation should share one request id.",
)
telemetry_parser.add_argument(
    "eventType",
    type=validate_event_type,
    location="json",
    required=True,
    help=f"The event type of the telemetry, should be either {EventType.START} or {EventType.END}.",
)
telemetry_parser.add_argument(
    "timestamp", type=str, location="json", required=True, help="The timestamp of the telemetry."
)
telemetry_parser.add_argument(
    "metadata", type=dict, location="json", required=True, help="The activity info of the telemetry."
)
telemetry_parser.add_argument(
    "firstCall",
    type=bool,
    location="json",
    required=False,
    default=True,
    help="Whether current activity is the first activity in the call chain.",
)


@api.route("/")
class Telemetry(Resource):
    @api.response(code=200, description="Create telemetry record", model=dict_field)
    @api.doc(parser=telemetry_parser, description="Create telemetry record")
    @local_user_only
    def post(self):
        from promptflow._sdk._telemetry import get_telemetry_logger, is_telemetry_enabled
        from promptflow._sdk._telemetry.activity import log_activity_end, log_activity_start

        if not is_telemetry_enabled():
            return make_response(jsonify({"message": "Telemetry is disabled."}), 400)

        args = telemetry_parser.parse_args()

        try:
            validate_metadata_based_on_event_type(args.metadata, args.eventType)
        except UserErrorException as exception:
            return make_response(
                jsonify({"errors": {"metadata": str(exception)}, "message": "Input payload validation failed"}), 400
            )

        activity_info = parse_activity_info(
            metadata=args.metadata,
            first_call=args.firstCall,
            user_agent=build_pfs_user_agent(),
            request_id=args[REQUEST_ID_KEY],
        )
        if args.eventType == EventType.START:
            log_activity_start(activity_info, get_telemetry_logger())
        elif args.eventType == EventType.END:
            log_activity_end(activity_info, get_telemetry_logger())
        return jsonify(
            {
                "status": ActivityCompletionStatus.SUCCESS,
            }
        )
