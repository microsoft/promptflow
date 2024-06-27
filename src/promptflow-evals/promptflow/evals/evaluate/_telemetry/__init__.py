# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import functools
import json
import logging
import inspect

import pandas as pd

from .._utils import _trace_destination_from_project_scope
from ..._user_agent import USER_AGENT
from promptflow.core import Prompty as prompty_core
from promptflow._sdk.entities._flows import Prompty as prompty_sdk, FlexFlow as flex_flow
from promptflow._sdk.entities._flows.dag import Flow as dag_flow
from promptflow.client import PFClient

LOGGER = logging.getLogger(__name__)


def _get_evaluator_type(evaluator):
    """
    Get evaluator type for telemetry. Possible values are "built-in", "custom" and "content-safety"
    """
    built_in = False
    content_safety = False

    module = inspect.getmodule(evaluator)
    built_in = (module and module.__name__.startswith("promptflow.evals.evaluators."))

    if built_in:
        content_safety = module.__name__.startswith("promptflow.evals.evaluators._content_safety")

    return "content-safety" if content_safety else "built-in" if built_in else "custom"


def _get_evaluator_properties(evaluator, evaluator_name):
    """
    Get evaluator properties for telemetry
    It gets name, pf_type, and type
    name : tries best to get the most meaningful name for the evaluator
    pf_type : The type of promptflow being used
    type : The type of evaluator being used. Possible values are "built-in", "custom" and "content-safety"
    """

    try:
        # Cover flex flow and prompty based evaluator
        if isinstance(evaluator, (prompty_sdk, prompty_core, flex_flow)):
            name = evaluator.name
            pf_type = evaluator.__class__.__name__
        # Cover dag flow based evaluator
        elif isinstance(evaluator, dag_flow):
            name = evaluator.name
            pf_type = "DagFlow"
        elif inspect.isfunction(evaluator):
            name = evaluator.__name__
            pf_type = flex_flow.__name__
        elif hasattr(evaluator, "__class__") and callable(evaluator):
            name = evaluator.__class__.__name__
            pf_type = flex_flow.__name__
        else:
            # fallback option
            name = str(evaluator)
            pf_type = "Unknown"
    except Exception as e:
        LOGGER.debug(f"Failed to get evaluator properties: {e}")
        name = str(evaluator)
        pf_type = "Unknown"

    return {
        "name": name,
        "pf_type": pf_type,
        "type": _get_evaluator_type(evaluator),
        "alias": evaluator_name if evaluator_name else ""
    }


# cspell:ignore isna
def log_evaluate_activity(func):
    """Decorator to log evaluate activity"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from promptflow._sdk._telemetry import ActivityType, log_activity
        from promptflow._sdk._telemetry.telemetry import get_telemetry_logger

        evaluators = kwargs.get("evaluators", [])
        azure_ai_project = kwargs.get("azure_ai_project", None)

        pf_client = PFClient(
            config={
                "trace.destination": _trace_destination_from_project_scope(
                    azure_ai_project)} if azure_ai_project else None,
            user_agent=USER_AGENT,
        )

        track_in_cloud = True if pf_client._config.get_trace_destination() else False
        evaluate_target = True if kwargs.get("target", None) else False
        evaluator_config = True if kwargs.get("evaluator_config", None) else False
        custom_dimensions = {
            "track_in_cloud": track_in_cloud,
            "evaluate_target": evaluate_target,
            "evaluator_config": evaluator_config,
        }

        with log_activity(get_telemetry_logger(), "pf.evals.evaluate", activity_type=ActivityType.PUBLICAPI,
                          user_agent=USER_AGENT, custom_dimensions=custom_dimensions):
            result = func(*args, **kwargs)

            try:
                evaluators_info = []
                for evaluator_name, evaluator in evaluators.items():
                    evaluator_info = _get_evaluator_properties(evaluator, evaluator_name)
                    try:
                        evaluator_df = pd.DataFrame(result.get("rows", [])).filter(like=f"outputs.{evaluator_name}",
                                                                                   axis=1)

                        failed_rows = evaluator_df.shape[0] if evaluator_df.empty else int(
                                                                    evaluator_df.isna().any(axis=1).sum())
                        total_rows = evaluator_df.shape[0]

                        evaluator_info["failed_rows"] = failed_rows
                        evaluator_info["total_rows"] = total_rows
                    except Exception as e:
                        LOGGER.debug(f"Failed to collect evaluate failed row info for {evaluator_name}: {e}")
                    evaluators_info.append(evaluator_info)

                custom_dimensions = {
                    "evaluators_info": json.dumps(evaluators_info)
                }
                with log_activity(get_telemetry_logger(), "pf.evals.evaluate_usage_info",
                                  activity_type=ActivityType.PUBLICAPI, user_agent=USER_AGENT,
                                  custom_dimensions=custom_dimensions):
                    pass
            except Exception as e:
                LOGGER.debug(f"Failed to collect evaluate usage info: {e}")

            return result

    return wrapper
