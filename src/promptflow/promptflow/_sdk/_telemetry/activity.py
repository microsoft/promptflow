# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import functools
import uuid
from contextvars import ContextVar
from datetime import datetime
import threading

from promptflow._sdk._telemetry.telemetry import TelemetryMixin
from promptflow.exceptions import _ErrorInfo
from promptflow._sdk._utils import ClientUserAgentUtil


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


@contextlib.contextmanager
def log_activity(
    logger,
    activity_name,
    activity_type=ActivityType.INTERNALCALL,
    custom_dimensions=None,
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
    :return: None
    """
    if not custom_dimensions:
        custom_dimensions = {}

    user_agent = ClientUserAgentUtil.get_user_agent()
    request_id = request_id_context.get()
    if not request_id:
        # public function call
        first_call = True
        request_id = str(uuid.uuid4())
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

    message = f"{activity_name}.start"
    logger.info(message, extra={"custom_dimensions": activity_info})
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
        try:
            if first_call:
                # recover request id in global storage
                request_id_context.set(None)
            end_time = datetime.utcnow()
            duration_ms = round((end_time - start_time).total_seconds() * 1000, 2)

            activity_info["completion_status"] = completion_status
            activity_info["duration_ms"] = duration_ms
            message = f"{activity_name}.complete"
            if exception:
                logger.error(message, extra={"custom_dimensions": activity_info})
            else:
                logger.info(message, extra={"custom_dimensions": activity_info})
        except Exception:  # pylint: disable=broad-except
            # skip if logger failed to log
            pass  # pylint: disable=lost-exception
        # raise the exception to align with the behavior of the with statement
        if exception:
            raise exception


def extract_telemetry_info(self):
    """Extract pf telemetry info from given telemetry mix-in instance."""
    result = {}
    try:
        if isinstance(self, TelemetryMixin):
            return self._get_telemetry_values()
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
            from promptflow._utils.version_hint_utils import hint_for_update, check_latest_version, HINT_ACTIVITY_NAME

            logger = get_telemetry_logger()

            custom_dimensions.update(extract_telemetry_info(self))
            # update activity name according to kwargs.
            _activity_name = update_activity_name(activity_name, kwargs=kwargs)
            with log_activity(logger, _activity_name, activity_type, custom_dimensions):
                if _activity_name in HINT_ACTIVITY_NAME:
                    hint_for_update()
                    # set check_latest_version as deamon thread to avoid blocking main thread
                    thread = threading.Thread(target=check_latest_version, daemon=True)
                    thread.start()
                return f(self, *args, **kwargs)

        return wrapper

    return monitor
