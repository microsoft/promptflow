# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from flask import jsonify, make_response, request
from flask_restx import fields

from promptflow._sdk._service import Namespace, Resource
from promptflow._sdk._service.utils.utils import build_pfs_user_agent, local_user_only
from promptflow._sdk._telemetry import ActivityCompletionStatus, ActivityType
from promptflow._utils.utils import camel_to_snake
from promptflow.exceptions import UserErrorException

api = Namespace("Telemetries", description="Telemetry Management")


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


metadata_model = api.model(
    "Metadata",
    {
        "activityName": fields.String(
            required=True,
            description="The name of the activity.",
            enum=[
                AllowedActivityName.FLOW_TEST,
                AllowedActivityName.FLOW_NODE_TEST,
                AllowedActivityName.GENERATE_TOOL_META,
            ],
        ),
        "activityType": fields.String(required=True, description="The type of the activity."),
        "completionStatus": fields.String(
            required=False,
            description="The completion status of the activity.",
            enum=[ActivityCompletionStatus.SUCCESS, ActivityCompletionStatus.FAILURE],
        ),
        "durationMs": fields.Integer(required=False, description="The duration of the activity in milliseconds."),
        "errorCategory": fields.String(required=False, description="The error category of the activity."),
        "errorType": fields.String(required=False, description="The error type of the activity."),
        "errorTarget": fields.String(required=False, description="The error target of the activity."),
        "errorMessage": fields.String(required=False, description="The error message of the activity."),
        "errorDetails": fields.String(required=False, description="The error details of the activity."),
    },
)

telemetry_model = api.model(
    "Telemetry",
    {
        "eventType": fields.String(
            required=True,
            description="The event type of the telemetry.",
            enum=[EventType.START, EventType.END],
        ),
        "timestamp": fields.DateTime(required=True, description="The timestamp of the telemetry."),
        "firstCall": fields.Boolean(
            required=False,
            default=True,
            description="Whether current activity is the first activity in the call chain.",
        ),
        "metadata": fields.Nested(metadata_model),
    },
)


@api.route("/")
class Telemetry(Resource):
    @api.header(REQUEST_ID_KEY, type=str)
    @api.response(code=200, description="Create telemetry record")
    @api.response(code=400, description="Input payload validation failed")
    @api.doc(description="Create telemetry record")
    @api.expect(telemetry_model)
    @local_user_only
    @api.response(code=403, description="Telemetry is disabled or X-Remote-User is not set.")
    def post(self):
        from promptflow._sdk._telemetry import get_telemetry_logger, is_telemetry_enabled
        from promptflow._sdk._telemetry.activity import log_activity_end, log_activity_start

        if not is_telemetry_enabled():
            return make_response(
                jsonify(
                    {
                        "message": "Telemetry is disabled, you may re-enable it "
                        "via `pf config set telemetry.enabled=true`."
                    }
                ),
                403,
            )

        request_id = request.headers.get(REQUEST_ID_KEY)

        try:
            validate_metadata_based_on_event_type(api.payload["metadata"], api.payload["eventType"])
        except UserErrorException as exception:
            return make_response(
                jsonify({"errors": {"metadata": str(exception)}, "message": "Input payload validation failed"}), 400
            )

        activity_info = parse_activity_info(
            metadata=api.payload["metadata"],
            first_call=api.payload.get("firstCall", True),
            user_agent=build_pfs_user_agent(),
            request_id=request_id,
        )
        if api.payload["eventType"] == EventType.START:
            log_activity_start(activity_info, get_telemetry_logger())
        elif api.payload["eventType"] == EventType.END:
            log_activity_end(activity_info, get_telemetry_logger())
        return jsonify(
            {
                "status": ActivityCompletionStatus.SUCCESS,
            }
        )
