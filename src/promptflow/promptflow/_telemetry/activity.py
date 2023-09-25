# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import functools
import uuid
from datetime import datetime

from promptflow._telemetry.telemetry import TelemetryMixin


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
    activity_info = {
        # TODO(2699383): use same request id with service caller
        "request_id": str(uuid.uuid4()),
        "activity_name": activity_name,
        "activity_type": activity_type,
    }
    custom_dimensions = custom_dimensions or {}
    activity_info.update(custom_dimensions)

    start_time = datetime.utcnow()
    completion_status = ActivityCompletionStatus.SUCCESS

    message = "ActivityStarted, {}".format(activity_name)
    logger.info(message, extra={"properties": activity_info})
    exception = None

    try:
        yield logger
    except BaseException as e:  # pylint: disable=broad-except
        exception = e
        completion_status = ActivityCompletionStatus.FAILURE
    finally:
        try:
            end_time = datetime.utcnow()
            duration_ms = round((end_time - start_time).total_seconds() * 1000, 2)

            activity_info["completion_status"] = completion_status
            activity_info["duration_ms"] = duration_ms
            message = "ActivityCompleted: Activity={}, HowEnded={}, Duration={} [ms]".format(
                activity_name, completion_status, duration_ms
            )
            if exception:
                logger.error(message, extra={"properties": activity_info})
            else:
                logger.info(message, extra={"properties": activity_info})
        except Exception:  # pylint: disable=broad-except
            return  # pylint: disable=lost-exception
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
            from promptflow._telemetry.telemetry import get_telemetry_logger

            logger = get_telemetry_logger()

            custom_dimensions.update(extract_telemetry_info(self))

            with log_activity(logger, activity_name, activity_type, custom_dimensions):
                return f(self, *args, **kwargs)

        return wrapper

    return monitor
