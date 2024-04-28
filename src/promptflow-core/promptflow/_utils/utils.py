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
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, TypeVar, Union

from promptflow._constants import DEFAULT_ENCODING, PF_LONG_RUNNING_LOGGING_INTERVAL
from promptflow._utils.logger_utils import bulk_logger
from promptflow.contracts.multimedia import PFBytes
from promptflow.contracts.types import AssistantDefinition

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


def load_list_from_jsonl(file: Union[str, Path]):
    content = []
    with open(file, "r", encoding=DEFAULT_ENCODING) as fin:
        for line in fin:
            content.append(json.loads(line))
    return content


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
    total_count: int,
    current_count: int,
    last_log_count: int,
    logger: logging.Logger = bulk_logger,
    formatter="Finished {count} / {total_count} lines.",
):
    """Log progress of the current execution. Return the last_log_count for the next iteration."""

    # Calculate log_interval to determine when to log progress.
    # If total_count is less than 100, log every 10% of total_count; otherwise, log every 10 lines.
    log_interval = min(10, max(int(total_count / 10), 1))

    # There are two situations that we will print the progress log:
    # 1. The difference between current_count and last_log_count exceeds log_interval.
    # 2. The current_count is evenly divisible by log_interval.
    log_flag = (current_count - last_log_count) >= log_interval or (
        current_count > last_log_count and current_count % log_interval == 0
    )

    if current_count > 0 and (log_flag or current_count == total_count):
        average_execution_time = round((datetime.utcnow().timestamp() - run_start_time.timestamp()) / current_count, 2)
        estimated_execution_time = round(average_execution_time * (total_count - current_count), 2)
        logger.info(formatter.format(count=current_count, total_count=total_count))
        logger.info(
            f"Average execution time for completed lines: {average_execution_time} seconds. "
            f"Estimated time for incomplete lines: {estimated_execution_time} seconds."
        )
        return current_count
    return last_log_count


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


def default_json_encoder(obj):
    if isinstance(obj, PFBytes):
        return obj.to_base64(with_type=True)
    if isinstance(obj, AssistantDefinition):
        return obj.serialize()
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _match_reference(env_val: str):
    env_val = env_val.strip()
    m = re.match(r"^\$\{([^.]+)\.([^.]+)}$", env_val)
    if not m:
        return None, None
    name, key = m.groups()
    return name, key


def copy_file_except(src_dir, dst_dir, exclude_file):
    """
    Copy all files from src_dir to dst_dir recursively, excluding a specific file
    directly under the root of src_dir.

    :param src_dir: Source directory path
    :type src_dir: str
    :param dst_dir: Destination directory path
    :type dst_dir: str
    :param exclude_file: Name of the file to exclude from copying
    :type exclude_file: str
    """
    os.makedirs(dst_dir, exist_ok=True)

    for root, dirs, files in os.walk(src_dir):
        rel_path = os.path.relpath(root, src_dir)
        current_dst_dir = os.path.join(dst_dir, rel_path)

        os.makedirs(current_dst_dir, exist_ok=True)

        for file in files:
            if rel_path == "." and file == exclude_file:
                continue  # Skip the excluded file
            src_file_path = os.path.join(root, file)
            dst_file_path = os.path.join(current_dst_dir, file)
            shutil.copy2(src_file_path, dst_file_path)


def in_jupyter_notebook() -> bool:
    """
    Checks if user is using a Jupyter Notebook. This is necessary because logging is not allowed in
    non-Jupyter contexts.

    Adapted from https://stackoverflow.com/a/22424821
    """
    try:  # cspell:ignore ipython
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True


def snake_to_camel(name):
    return re.sub(r"(?:^|_)([a-z])", lambda x: x.group(1).upper(), name)


def prepare_folder(path: Union[str, Path]) -> Path:
    """Create folder if not exists and return the folder path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def try_get_long_running_logging_interval(logger: logging.Logger, default_interval: int):
    logging_interval_in_env = os.environ.get(PF_LONG_RUNNING_LOGGING_INTERVAL, None)
    if logging_interval_in_env:
        try:
            value = int(logging_interval_in_env)
            if value <= 0:
                raise ValueError
            logger.info(
                f"Using value of {PF_LONG_RUNNING_LOGGING_INTERVAL} in environment variable as "
                f"logging interval: {logging_interval_in_env}"
            )
            return value
        except ValueError:
            logger.warning(
                f"Value of {PF_LONG_RUNNING_LOGGING_INTERVAL} in environment variable "
                f"('{logging_interval_in_env}') is invalid, use default value {default_interval}"
            )
            return default_interval
    # If the environment variable is not set, return none to disable the long running logging
    return None


def strip_quotation(value):
    """
    To avoid escaping chars in command args, args will be surrounded in quotas.
    Need to remove the pair of quotation first.
    """
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    else:
        return value


def is_empty_target(obj: Optional[Dict]) -> bool:
    """Determines if it's empty target

    :param obj: The object to check
    :type obj: Optional[Dict]
    :return: True if obj is None or an empty Dict
    :rtype: bool
    """
    return (
        obj is None
        # some objs have overloaded "==" and will cause error. e.g CommandComponent obj
        or (isinstance(obj, dict) and len(obj) == 0)
    )


def convert_ordered_dict_to_dict(target_object: Union[Dict, List], remove_empty: bool = True) -> Union[Dict, List]:
    """Convert ordered dict to dict. Remove keys with None value.
    This is a workaround for rest request must be in dict instead of
    ordered dict.

    :param target_object: The object to convert
    :type target_object: Union[Dict, List]
    :param remove_empty: Whether to omit values that are None or empty dictionaries. Defaults to True.
    :type remove_empty: bool
    :return: Converted ordered dict with removed None values
    :rtype: Union[Dict, List]
    """
    # OrderedDict can appear nested in a list
    if isinstance(target_object, list):
        new_list = []
        for item in target_object:
            item = convert_ordered_dict_to_dict(item, remove_empty=remove_empty)
            if not is_empty_target(item) or not remove_empty:
                new_list.append(item)
        return new_list
    if isinstance(target_object, dict):
        new_dict = {}
        for key, value in target_object.items():
            value = convert_ordered_dict_to_dict(value, remove_empty=remove_empty)
            if not is_empty_target(value) or not remove_empty:
                new_dict[key] = value
        return new_dict
    return target_object
