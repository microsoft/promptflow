# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from flask import jsonify, make_response, request

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


def parse_activity_info(telemetry_data, user_agent, request_id):
    first_call = telemetry_data.get("firstCall", True)
    request_id = request_id

    return {
        "request_id": request_id,
        "first_call": first_call,
        "user_agent": user_agent,
        **_dict_camel_to_snake(telemetry_data.get("metadata", {})),
    }


def validate_telemetry_payload(payload, headers):
    if REQUEST_ID_KEY not in headers:
        raise UserErrorException(f"Missing {REQUEST_ID_KEY} in request header.")

    if not all(key in payload for key in ("eventType", "timestamp", "metadata")):
        missing_fields = {"eventType", "timestamp", "metadata"} - set(payload.keys())
        raise UserErrorException(f"Missing required fields in telemetry payload: {', '.join(missing_fields)}")
    if payload.get("eventType") not in (EventType.START, EventType.END):
        raise UserErrorException(f"Invalid eventType: {payload.get('eventType')}")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise UserErrorException(f"Invalid metadata: {metadata}")
    if metadata.get("activityName") not in [
        AllowedActivityName.FLOW_TEST,
        AllowedActivityName.FLOW_NODE_TEST,
        AllowedActivityName.GENERATE_TOOL_META,
    ]:
        raise UserErrorException(f"Invalid activityName: {metadata.get('activityName')}")
    if metadata.get("activityType") not in [
        ActivityType.INTERNALCALL,
        ActivityType.PUBLICAPI,
    ]:
        raise UserErrorException(f"Invalid activityType: {metadata.get('activityType')}")

    if payload.get("eventType") == EventType.END:
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


@api.route("/")
class Telemetry(Resource):
    @api.response(code=200, description="Create telemetry record", model=dict_field)
    @api.doc(description="Create telemetry record")
    @local_user_only
    def post(self):
        """Private API to create telemetry record directly.
        Telemetry details should be in the request body; will append an extra User-Agent
        to the original one in the request header.
        Request id must be put in "x-ms-promptflow-request-id" in request header.
        Request body should be in json format, e.g.:
        {
            "eventType": "Start",
            "timestamp": "2021-09-29T22:51:00.000Z",
            "metadata": {
                "activityName": "activity_name",
                "activityType": "activity_type",
            }
        }
        """
        from promptflow._sdk._telemetry import get_telemetry_logger, is_telemetry_enabled
        from promptflow._sdk._telemetry.activity import log_activity_end, log_activity_start

        if not is_telemetry_enabled():
            return make_response(jsonify({"error": "Telemetry is disabled."}), 400)

        telemetry_data = request.get_json(force=True)
        try:
            validate_telemetry_payload(telemetry_data, request.headers)
        except UserErrorException as exception:
            return make_response(jsonify({"error": f"Invalid telemetry payload: {exception}"}), 400)

        activity_info = parse_activity_info(
            telemetry_data, user_agent=build_pfs_user_agent(), request_id=request.headers.get(REQUEST_ID_KEY)
        )
        if telemetry_data.get("eventType") == EventType.START:
            log_activity_start(activity_info, get_telemetry_logger())
        elif telemetry_data.get("eventType") == EventType.END:
            log_activity_end(activity_info, get_telemetry_logger())
        return jsonify(
            {
                "status": ActivityCompletionStatus.SUCCESS,
            }
        )
