# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""This is a common util file.
!!!Please do not include any project related import.!!!
"""
import contextlib
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

from promptflow._constants import DEFAULT_ENCODING

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


def is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except TypeError:
        return False


def load_json(file_path: Union[str, Path]) -> dict:
    if os.path.getsize(file_path) > 0:
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


def dump_list_to_jsonl(file_path: Union[str, Path], list_data: List[Dict]):
    with open(file_path, "w", encoding=DEFAULT_ENCODING) as jsonl_file:
        for data in list_data:
            json.dump(data, jsonl_file, ensure_ascii=False)
            jsonl_file.write("\n")


def transpose(values: List[Dict[str, Any]], keys: Optional[List] = None) -> Dict[str, List]:
    keys = keys or list(values[0].keys())
    return {key: [v.get(key) for v in values] for key in keys}


def reverse_transpose(values: Dict[str, List]) -> List[Dict[str, Any]]:
    # Setup a result list same len with values
    value_lists = list(values.values())
    _len = len(value_lists[0])
    if any(len(value_list) != _len for value_list in value_lists):
        raise Exception(f"Value list of each key must have same length, please check {values!r}.")
    result = []
    for i in range(_len):
        result.append({})
    for key, vals in values.items():
        for _idx, val in enumerate(vals):
            result[_idx][key] = val
    return result


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
    inputs: Iterable[T], logger: logging.Logger, total_count: int, formatter="{count} / {total_count} finished."
) -> Iterator[T]:
    log_interval = max(int(total_count / 10), 1)
    count = 0
    for item in inputs:
        count += 1
        if count % log_interval == 0 or count == total_count:
            logger.info(formatter.format(count=count, total_count=total_count))

        yield item


def log_progress(
    run_start_time: datetime,
    logger: logging.Logger,
    count: int,
    total_count: int,
    formatter="Finished {count} / {total_count} lines.",
    *,
    last_log_count: Optional[int] = None,
):
    # Calculate log_interval to determine when to log progress.
    # If total_count is less than 100, log every 10% of total_count; otherwise, log every 10 lines.
    log_interval = min(10, max(int(total_count / 10), 1))

    # If last_log_count is not None, determine whether to log based on whether the difference
    # between the current count and the previous count exceeds log_interval.
    # Otherwise, decide based on whether the current count is evenly divisible by log_interval.
    if last_log_count:
        log_flag = (count - last_log_count) >= log_interval
    else:
        log_flag = count % log_interval == 0

    if count > 0 and (log_flag or count == total_count):
        average_execution_time = round((datetime.utcnow().timestamp() - run_start_time.timestamp()) / count, 2)
        estimated_execution_time = round(average_execution_time * (total_count - count), 2)
        logger.info(formatter.format(count=count, total_count=total_count))
        logger.info(
            f"Average execution time for completed lines: {average_execution_time} seconds. "
            f"Estimated time for incomplete lines: {estimated_execution_time} seconds."
        )


def extract_user_frame_summaries(frame_summaries: List[traceback.FrameSummary]):
    from promptflow import _core

    core_folder = os.path.dirname(_core.__file__)

    for i in range(len(frame_summaries) - 1):
        cur_file = frame_summaries[i].filename
        next_file = frame_summaries[i + 1].filename
        # If the current frame is in _core folder and the next frame is not in _core folder
        # then we can say that the next frame is in user code.
        if cur_file.startswith(core_folder) and not next_file.startswith(core_folder):
            return frame_summaries[i + 1 :]
    return frame_summaries


def format_user_stacktrace(frame):
    #  TODO: Maybe we can filter all frames from our code base to make it clean?
    frame_summaries = traceback.extract_stack(frame)
    user_frame_summaries = extract_user_frame_summaries(frame_summaries)
    return traceback.format_list(user_frame_summaries)


def generate_elapsed_time_messages(func_name: str, start_time: float, interval: int, thread_id: int):
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


def set_context(context: contextvars.Context):
    for var, value in context.items():
        var.set(value)


def convert_inputs_mapping_to_param(inputs_mapping: dict):
    """Use this function to convert inputs_mapping to a string that can be passed to component as a string parameter,
    we have to do this since we can't pass a dict as a parameter to component.
    # TODO: Finalize the format of inputs_mapping
    """
    return ",".join([f"{k}={v}" for k, v in inputs_mapping.items()])


@contextlib.contextmanager
def environment_variable_overwrite(key, val):
    if key in os.environ.keys():
        backup_value = os.environ[key]
    else:
        backup_value = None
    os.environ[key] = val

    try:
        yield
    finally:
        if backup_value:
            os.environ[key] = backup_value
        else:
            os.environ.pop(key)


def resolve_dir_to_absolute(base_dir: Union[str, Path], sub_dir: Union[str, Path]) -> Path:
    """Resolve directory to absolute path with base_dir as root"""
    path = sub_dir if isinstance(sub_dir, Path) else Path(sub_dir)
    if not path.is_absolute():
        base_dir = base_dir if isinstance(base_dir, Path) else Path(base_dir)
        path = base_dir / sub_dir
    return path


def parse_ua_to_dict(ua):
    """Parse string user agent to dict with name as ua name and value as ua version."""
    ua_dict = {}
    ua_list = ua.split(" ")
    for item in ua_list:
        if item:
            key, value = item.split("/")
            ua_dict[key] = value
    return ua_dict


# TODO: Add "conditions" parameter to pass in a list of lambda functions
# to check if the environment variable is valid.
def get_int_env_var(env_var_name, default_value=None):
    """
    The function `get_int_env_var` retrieves an integer environment variable value, with an optional
    default value if the variable is not set or cannot be converted to an integer.

    :param env_var_name: The name of the environment variable you want to retrieve the value of
    :param default_value: The default value is the value that will be returned if the environment
    variable is not found or if it cannot be converted to an integer
    :return: an integer value.
    """
    try:
        return int(os.environ.get(env_var_name, default_value))
    except Exception:
        return default_value


def prompt_y_n(msg, default=None):
    if default not in [None, "y", "n"]:
        raise ValueError("Valid values for default are 'y', 'n' or None")
    y = "Y" if default == "y" else "y"
    n = "N" if default == "n" else "n"
    while True:
        ans = prompt_input("{} ({}/{}): ".format(msg, y, n))
        if ans.lower() == n.lower():
            return False
        if ans.lower() == y.lower():
            return True
        if default and not ans:
            return default == y.lower()


def prompt_input(msg):
    return input("\n===> " + msg)


def _normalize_identifier_name(name):
    normalized_name = name.lower()
    normalized_name = re.sub(r"[\W_]", " ", normalized_name)  # No non-word characters
    normalized_name = re.sub(" +", " ", normalized_name).strip()  # No double spaces, leading or trailing spaces
    if re.match(r"\d", normalized_name):
        normalized_name = "n" + normalized_name  # No leading digits
    return normalized_name


def _sanitize_python_variable_name(name: str):
    return _normalize_identifier_name(name).replace(" ", "_")
