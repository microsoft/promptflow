# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import functools
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict

from promptflow._sdk._telemetry.telemetry import TelemetryMixin
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow.exceptions import _ErrorInfo


class ActivityType(object):
    """The type of activity (code) monitored.

    The default type is "PublicAPI".
    """

    PUBLICAPI = "PublicApi"  # incoming public API call (default)
    INTERNALCALL = "InternalCall"  # internal (function) call
    CLIENTPROXY = "ClientProxy"  # an outgoing service API call


class ActivityCompletionStatus(object):
    """The activity (code) completion status, success, or failure."""

    SUCCESS = "Success"
    FAILURE = "Failure"


request_id_context = ContextVar("request_id_context", default=None)


def log_activity_start(activity_info: Dict[str, Any], logger) -> None:
    """Log activity start.
    Sample activity_info:
    {
        "request_id": "request_id",
        "first_call": True,
        "activity_name": "activity_name",
        "activity_type": "activity_type",
        "user_agent": "user_agent",
    }

    :param activity_info: The custom properties of the activity to record.
    :type activity_info: dict
    :param logger: The logger adapter.
    :type logger: logging.LoggerAdapter
    """
    message = f"{activity_info['activity_name']}.start"
    logger.info(message, extra={"custom_dimensions": activity_info})
    pass


def log_activity_end(activity_info: Dict[str, Any], logger) -> None:
    """Log activity end.
    Sample activity_info for success (start info plus run info):
    {
        ...,
        "duration_ms": 1000
        "completion_status": "Success",
    }
    Sample activity_info for failure (start info plus error info):
    {
        ...,
        "duration_ms": 1000
        "completion_status": "Failure",
        "error_category": "error_category",
        "error_type": "error_type",
        "error_target": "error_target",
        "error_message": "error_message",
        "error_detail": "error_detail"
    }
    Error target & error type can be found in the following link:
    https://github.com/microsoft/promptflow/blob/main/src/promptflow/promptflow/exceptions.py

    :param activity_info: The custom properties of the activity.
    :type activity_info: dict
    :param logger: The logger adapter.
    :type logger: logging.LoggerAdapter
    """
    try:
        # we will fail this log if activity_name/completion_status is not in activity_info, so directly use get()
        message = f"{activity_info['activity_name']}.complete"
        if activity_info["completion_status"] == ActivityCompletionStatus.FAILURE:
            logger.error(message, extra={"custom_dimensions": activity_info})
        else:
            logger.info(message, extra={"custom_dimensions": activity_info})
    except Exception:  # pylint: disable=broad-except
        # skip if logger failed to log
        pass  # pylint: disable=lost-exception


def generate_request_id():
    return str(uuid.uuid4())


@contextlib.contextmanager
def log_activity(
    logger,
    activity_name,
    activity_type=ActivityType.INTERNALCALL,
    custom_dimensions=None,
    user_agent=None,
):
    """Log an activity.

    An activity is a logical block of code that consumers want to monitor.
    To monitor, wrap the logical block of code with the ``log_activity()`` method. As an alternative, you can
    also use the ``@monitor_with_activity`` decorator.

    :param logger: The logger adapter.
    :type logger: logging.LoggerAdapter
    :param activity_name: The name of the activity. The name should be unique per the wrapped logical code block.
    :type activity_name: str
    :param activity_type: One of PUBLICAPI, INTERNALCALL, or CLIENTPROXY which represent an incoming API call,
        an internal (function) call, or an outgoing API call. If not specified, INTERNALCALL is used.
    :type activity_type: str
    :param custom_dimensions: The custom properties of the activity.
    :type custom_dimensions: dict
    :param user_agent: Specify user agent. If not specified, the user agent will be got from OperationContext.
    :type user_agent: str
    :return: None
    """
    if not custom_dimensions:
        custom_dimensions = {}

    # provided user agent will be respected even if it's ""
    if user_agent is None:
        user_agent = ClientUserAgentUtil.get_user_agent()
    request_id = request_id_context.get()
    if not request_id:
        # public function call
        first_call = True
        request_id = generate_request_id()
        request_id_context.set(request_id)
    else:
        first_call = False

    activity_info = {
        "request_id": request_id,
        "first_call": first_call,
        "activity_name": activity_name,
        "activity_type": activity_type,
        "user_agent": user_agent,
    }
    activity_info.update(custom_dimensions)

    start_time = datetime.utcnow()
    completion_status = ActivityCompletionStatus.SUCCESS

    log_activity_start(activity_info, logger)
    exception = None

    try:
        yield logger
    except BaseException as e:  # pylint: disable=broad-except
        exception = e
        completion_status = ActivityCompletionStatus.FAILURE
        error_category, error_type, error_target, error_message, error_detail = _ErrorInfo.get_error_info(exception)
        activity_info["error_category"] = error_category
        activity_info["error_type"] = error_type
        activity_info["error_target"] = error_target
        activity_info["error_message"] = error_message
        activity_info["error_detail"] = error_detail
    finally:
        if first_call:
            # recover request id in global storage
            request_id_context.set(None)

        end_time = datetime.utcnow()
        duration_ms = round((end_time - start_time).total_seconds() * 1000, 2)

        activity_info["completion_status"] = completion_status
        activity_info["duration_ms"] = duration_ms

        log_activity_end(activity_info, logger)
        # raise the exception to align with the behavior of the with statement
        if exception:
            raise exception


def extract_telemetry_info(self, *args, **kwargs):
    """Extract pf telemetry info from given telemetry mix-in instance."""
    result = {}
    try:
        if isinstance(self, TelemetryMixin):
            return self._get_telemetry_values(*args, **kwargs)
    except Exception:
        pass
    return result


def update_activity_name(activity_name, kwargs=None, args=None):
    """Update activity name according to kwargs. For flow test, we want to know if it's node test."""
    if activity_name == "pf.flows.test":
        # SDK
        if kwargs.get("node", None):
            activity_name = "pf.flows.node_test"
    elif activity_name == "pf.flow.test":
        # CLI
        if getattr(args, "node", None):
            activity_name = "pf.flow.node_test"
    return activity_name


def monitor_operation(
    activity_name,
    activity_type=ActivityType.INTERNALCALL,
    custom_dimensions=None,
):
    """A wrapper for monitoring an activity in operations class.

    To monitor, use the ``@monitor_operation`` decorator.
    Note: this decorator should only use in operations class methods.

    :param activity_name: The name of the activity. The name should be unique per the wrapped logical code block.
    :type activity_name: str
    :param activity_type: One of PUBLICAPI, INTERNALCALL, or CLIENTPROXY which represent an incoming API call,
        an internal (function) call, or an outgoing API call. If not specified, INTERNALCALL is used.
    :type activity_type: str
    :param custom_dimensions: The custom properties of the activity.
    :type custom_dimensions: dict
    :return:
    """
    if not custom_dimensions:
        custom_dimensions = {}

    def monitor(f):
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            from promptflow._sdk._telemetry.telemetry import get_telemetry_logger
            from promptflow._sdk._version_hint_utils import HINT_ACTIVITY_NAME, check_latest_version, hint_for_update

            logger = get_telemetry_logger()

            if "activity_name" not in kwargs:
                custom_dimensions.update(extract_telemetry_info(self, *args, **kwargs, activity_name=activity_name))
            else:
                custom_dimensions.update(extract_telemetry_info(self, *args, **kwargs))

            if isinstance(self, TelemetryMixin):
                user_agent = self._get_user_agent_override()
            else:
                user_agent = None

            # update activity name according to kwargs.
            _activity_name = update_activity_name(activity_name, kwargs=kwargs)
            with log_activity(
                logger=logger,
                activity_name=_activity_name,
                activity_type=activity_type,
                custom_dimensions=custom_dimensions,
                user_agent=user_agent,
            ):
                if _activity_name in HINT_ACTIVITY_NAME:
                    hint_for_update()
                    # set check_latest_version as deamon thread to avoid blocking main thread
                    thread = threading.Thread(target=check_latest_version, daemon=True)
                    thread.start()
                return f(self, *args, **kwargs)

        return wrapper

    return monitor
