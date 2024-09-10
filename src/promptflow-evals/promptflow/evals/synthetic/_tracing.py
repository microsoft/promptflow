# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=C0103,C0114,C0116,E0401,E0611

import functools

from promptflow._sdk._telemetry.activity import ActivityType, monitor_operation


def monitor_adversarial_scenario(activity_name: str = "adversarial.simulator.call"):
    """
    Monitor an adversarial scenario.

    Parameters:
    activity_name (str): The name of the activity to monitor.
    """

    def decorator(func):
        """
        Decorator for monitoring an adversarial scenario.

        Parameters:
        func (function): The function to be decorated.
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrapper for monitoring an adversarial scenario.

            Parameters:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
            """
            scenario = str(kwargs.get("scenario", None))
            max_conversation_turns = kwargs.get("max_conversation_turns", None)
            max_simulation_results = kwargs.get("max_simulation_results", None)
            jailbreak = kwargs.get("jailbreak", None)
            decorated_func = monitor_operation(
                activity_name=activity_name,
                activity_type=ActivityType.PUBLICAPI,
                custom_dimensions={
                    "scenario": scenario,
                    "max_conversation_turns": max_conversation_turns,
                    "max_simulation_results": max_simulation_results,
                    "jailbreak": jailbreak,
                },
            )(func)

            return decorated_func(*args, **kwargs)

        return wrapper

    return decorator


def monitor_task_simulator(func):
    """
    Monitor a task simulator.

    Parameters:
    func (function): The function to be decorated.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        """
        Wrapper for monitoring a task simulator.

        Parameters:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
        """
        text_length = len(kwargs.get("text", ""))
        user_persona_length = len(kwargs.get("user_persona", []))
        num_queries = kwargs.get("num_queries", 0)
        max_conversation_turns = kwargs.get("max_conversation_turns", 0)
        decorated_func = monitor_operation(
            activity_name="task.simulator.call",
            activity_type=ActivityType.PUBLICAPI,
            custom_dimensions={
                "text_length": text_length,
                "user_persona_length": user_persona_length,
                "number_of_queries": num_queries,
                "max_conversation_turns": max_conversation_turns,
            },
        )(func)

        return decorated_func(*args, **kwargs)

    return wrapper
