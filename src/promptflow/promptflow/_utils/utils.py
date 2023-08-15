# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""This is a common util file.
!!!Please do not include any project related import.!!!
"""
import contextvars
import functools
import importlib
import json
import logging
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, TypeVar, Union

T = TypeVar("T")


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        if item in self:
            return self.__getitem__(item)
        return super().__getattribute__(item)


def camel_to_snake(text: str) -> Optional[str]:
    text = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", text).lower()


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


def get_string_size(content: str) -> int:
    """Get the size of content"""
    return len(content.encode("utf-8"))


def load_json(file_path: Union[str, Path]) -> dict:
    with open(file_path, "r") as f:
        return json.load(f)


def transpose(
    values: List[Dict[str, Any]], keys: Optional[List] = None
) -> Dict[str, List]:
    keys = keys or list(values[0].keys())
    return {key: [v.get(key) for v in values] for key in keys}


def reverse_transpose(values: Dict[str, List]) -> List[Dict[str, Any]]:
    # Setup a result list same len with values
    value_lists = list(values.values())
    _len = len(value_lists[0])
    if any(len(value_list) != _len for value_list in value_lists):
        raise Exception(
            f"Value list of each key must have same length, please check {values!r}."
        )
    result = []
    for i in range(_len):
        result.append({})
    for key, vals in values.items():
        for _idx, val in enumerate(vals):
            result[_idx][key] = val
    return result


def get_mlflow_tracking_uri(
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
    mt_endpoint: str,
) -> str:
    """Get the full mlflow tracking uri"""
    # "https://master.api.azureml-test.ms" to "azureml://master.api.azureml-test.ms"
    return (
        f"{mt_endpoint.replace('https', 'azureml')}/mlflow/v1.0/subscriptions/{subscription_id}/"
        f"resourceGroups/{resource_group_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"
    )


def deprecated(f=None, replace=None, version=None):
    if f is None:
        return functools.partial(deprecated, replace=replace, version=version)

    msg = [f"Function {f.__qualname__!r} is deprecated."]

    if version:
        msg.append(f"Deprecated since version {version}.")
    if replace:
        msg.append(f"Use {replace!r} instead.")
    msg = " ".join(msg)

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        logging.warning(msg)
        return f(*args, **kwargs)

    return wrapper


def try_import(module, error_message, raise_error=True):
    try:
        importlib.import_module(module)
    except ImportError as e:
        ex_message = f"{error_message} Root cause: {e!r}"
        logging.warning(ex_message)
        if raise_error:
            raise Exception(ex_message)


def is_in_ci_pipeline():
    if os.environ.get("IS_IN_CI_PIPELINE") == "true":
        return True
    return False


def count_and_log_progress(
    inputs: Iterable[T],
    logger: logging.Logger,
    total_count: int,
    formatter="{count} / {total_count} finished.",
) -> Iterator[T]:
    log_interval = max(int(total_count / 10), 1)
    count = 0
    for item in inputs:
        count += 1
        if count % log_interval == 0 or count == total_count:
            logger.info(formatter.format(count=count, total_count=total_count))

        yield item


def extract_user_frame_summaries(frame_summaries: List[traceback.FrameSummary]):
    from promptflow._core import flow_execution_context

    i = len(frame_summaries) - 1
    while i > 0:
        frame_summary = frame_summaries[i]
        if frame_summary.filename == flow_execution_context.__file__:
            return frame_summaries[i + 1 :]
        i -= 1
    return frame_summaries


def format_user_stacktrace(frame):
    #  TODO: Maybe we can filter all frames from our code base to make it clean?
    frame_summaries = traceback.extract_stack(frame)
    user_frame_summaries = extract_user_frame_summaries(frame_summaries)
    return traceback.format_list(user_frame_summaries)


def generate_elapsed_time_messages(
    func_name: str, start_time: float, interval: int, thread_id: int
):
    import sys

    frames = sys._current_frames()
    if thread_id not in frames:
        thread_msg = (
            f"thread {thread_id} cannot be found in sys._current_frames, "
            + "maybe it has been terminated due to unexpected errors."
        )
    else:
        frame = frames[thread_id]
        stack_msgs = format_user_stacktrace(frame)
        stack_msg = "".join(stack_msgs)
        thread_msg = f"stacktrace of thread {thread_id}:\n{stack_msg}"
    elapse_time = time.perf_counter() - start_time
    # Make elapse time a multiple of interval.
    elapse_time = round(elapse_time / interval) * interval
    msgs = [f"{func_name} has been running for {elapse_time:.0f} seconds, {thread_msg}"]
    return msgs


def _get_default_credential():
    """get default credential for current compute, cache the result to minimize actual token request count sent"""
    if is_in_ci_pipeline():
        from azure.identity import AzureCliCredential

        cred = AzureCliCredential()
    else:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    return cred


def set_context(context: contextvars.Context):
    for var, value in context.items():
        var.set(value)


def get_runtime_version():
    build_info = os.environ.get("BUILD_INFO", "")
    try:
        build_info_dict = json.loads(build_info)
        return build_info_dict["build_number"]
    except Exception:
        return "unknown"


def convert_inputs_mapping_to_param(inputs_mapping: dict):
    """Use this function to convert inputs_mapping to a string that can be passed to component as a string parameter,
    we have to do this since we can't pass a dict as a parameter to component.
    # TODO: Finalize the format of inputs_mapping
    """
    return ",".join([f"{k}={v}" for k, v in inputs_mapping.items()])
