# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import contextlib
import json
import os
import shutil
import sys
import traceback
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pydash
from dotenv import load_dotenv
from tabulate import tabulate

from promptflow._sdk._constants import DEFAULT_ENCODING, AzureMLWorkspaceTriad, CLIListOutputFormat
from promptflow._sdk._telemetry import ActivityType, get_telemetry_logger, log_activity
from promptflow._sdk._utilities.general_utils import print_red_error, print_yellow_warning
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.core._utils import get_workspace_triad_from_local as core_get_workspace_triad_from_local
from promptflow.exceptions import PromptflowException, UserErrorException

logger = get_cli_sdk_logger()


def _set_workspace_argument_for_subparsers(subparser, required=False):
    """Add workspace arguments to subparsers."""
    # Make these arguments optional so that user can use local azure cli context
    subparser.add_argument(
        "--subscription", required=required, type=str, help="Subscription id, required when pass run id."
    )
    subparser.add_argument(
        "--resource-group", "-g", required=required, type=str, help="Resource group name, required when pass run id."
    )
    subparser.add_argument(
        "--workspace-name", "-w", required=required, type=str, help="Workspace name, required when pass run id."
    )


def dump_connection_file(dot_env_file: str):
    for key in ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_BASE", "CHAT_DEPLOYMENT_NAME"]:
        if key not in os.environ:
            # skip dump connection file if not all required environment variables are set
            return

    connection_file_path = "./connection.json"
    os.environ["PROMPTFLOW_CONNECTIONS"] = connection_file_path

    load_dotenv(dot_env_file)
    connection_dict = {
        "custom_connection": {
            "type": "CustomConnection",
            "value": {
                "AZURE_OPENAI_API_KEY": os.environ["AZURE_OPENAI_API_KEY"],
                "AZURE_OPENAI_API_BASE": os.environ["AZURE_OPENAI_API_BASE"],
                "CHAT_DEPLOYMENT_NAME": os.environ["CHAT_DEPLOYMENT_NAME"],
            },
            "module": "promptflow.connections",
        }
    }
    with open(connection_file_path, "w") as f:
        json.dump(connection_dict, f)


def get_workspace_triad_from_local() -> AzureMLWorkspaceTriad:
    subscription_id, resource_group_name, workspace_name = core_get_workspace_triad_from_local()
    return AzureMLWorkspaceTriad(subscription_id, resource_group_name, workspace_name)


def confirm(question, skip_confirm) -> bool:
    if skip_confirm:
        return True
    answer = input(f"{question} [y/n]")
    while answer.lower() not in ["y", "n"]:
        answer = input("Please input 'y' or 'n':")
    return answer.lower() == "y"


@contextlib.contextmanager
def inject_sys_path(path):
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path = original_sys_path


def activate_action(name, description, epilog, add_params, subparsers, help_message, action_param_name="action"):
    parser = subparsers.add_parser(
        name,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=help_message,
    )
    if add_params:
        for add_param_func in add_params:
            add_param_func(parser)
    parser.set_defaults(**{action_param_name: name})
    return parser


def _dump_entity_with_warnings(entity) -> Dict:
    if not entity:
        return
    if isinstance(entity, Dict):
        return entity
    try:
        return entity._to_dict()  # type: ignore
    except Exception as err:
        logger.warning("Failed to deserialize response: " + str(err))
        logger.warning(str(entity))
        logger.debug(traceback.format_exc())


def list_of_dict_to_dict(obj: list):
    if not isinstance(obj, list):
        return {}
    result = {}
    for item in obj:
        result.update(item)
    return result


def list_of_dict_to_nested_dict(obj: list):
    result = {}
    for item in obj:
        for keys, value in item.items():
            keys = keys.split(".")
            pydash.set_(result, keys, value)
    return result


def _build_sorted_column_widths_tuple_list(
    columns: List[str],
    values1: Dict[str, int],
    values2: Dict[str, int],
    margins: Dict[str, int],
) -> List[Tuple[str, int]]:
    res = []
    for column in columns:
        value = max(values1[column], values2[column]) + margins[column]
        res.append((column, value))
    res.sort(key=lambda x: x[1], reverse=True)
    return res


def _assign_available_width(
    column_expected_widths: List[Tuple[str, int]],
    available_width: int,
    column_assigned_widths: Dict[str, int],
    average_width: Optional[int] = None,
) -> Tuple[int, Dict[str, int]]:
    for column, expected_width in column_expected_widths:
        if available_width <= 0:
            break
        target = average_width if average_width is not None else column_assigned_widths[column]
        delta = expected_width - target
        if delta <= available_width:
            column_assigned_widths[column] = expected_width
            available_width -= delta
        else:
            column_assigned_widths[column] += available_width
            available_width = 0
    return available_width, column_assigned_widths


def _calculate_column_widths(df: "DataFrame", terminal_width: int) -> List[int]:
    num_rows, num_columns = len(df), len(df.columns)
    index_column_width = max(len(str(num_rows)) + 2, 4)  # tabulate index column min width is 4
    terminal_width_buffer = 10
    available_width = terminal_width - terminal_width_buffer - index_column_width - (num_columns + 2)
    avg_available_width = available_width // num_columns

    header_widths, content_avg_widths, content_max_widths, column_margin = {}, {}, {}, {}
    for column in df.columns:
        header_widths[column] = len(column)
        contents = []
        for value in df[column]:
            contents.append(len(str(value)))
        content_avg_widths[column] = sum(contents) // len(contents)
        content_max_widths[column] = max(contents)
        # if header is longer than the longest content, the margin is 4; otherwise is 2
        # so we need to record this for every column
        if header_widths[column] >= content_max_widths[column]:
            column_margin[column] = 4
        else:
            column_margin[column] = 2

    column_widths = {}
    # first round: try to meet the average(or column header) width
    # record columns that need more width, we will deal with them in second round if we still have width
    round_one_left_columns = []
    for column in df.columns:
        expected_width = max(header_widths[column], content_avg_widths[column]) + column_margin[column]
        if avg_available_width <= expected_width:
            column_widths[column] = avg_available_width
            round_one_left_columns.append(column)
        else:
            column_widths[column] = expected_width

    current_available_width = available_width - sum(column_widths.values())
    if current_available_width > 0:
        # second round: assign left available width to those columns that need more
        # assign with greedy, sort recorded columns first from longest to shortest;
        # iterate and try to meet each column's expected width
        column_avg_tuples = _build_sorted_column_widths_tuple_list(
            round_one_left_columns, header_widths, content_avg_widths, column_margin
        )
        current_available_width, column_widths = _assign_available_width(
            column_avg_tuples, current_available_width, column_widths, avg_available_width
        )

    if current_available_width > 0:
        # third round: if there are still left available width, assign to try to meet the max width
        # still use greedy, sort first and iterate through all columns
        column_max_tuples = _build_sorted_column_widths_tuple_list(
            df.columns, header_widths, content_max_widths, column_margin
        )
        current_available_width, column_widths = _assign_available_width(
            column_max_tuples, current_available_width, column_widths
        )

    max_col_widths = [index_column_width]  # index column
    max_col_widths += [max(column_widths[column] - column_margin[column], 1) for column in df.columns]  # sub margin
    return max_col_widths


def pretty_print_dataframe_as_table(df: "DataFrame") -> None:
    # try to get terminal window width
    try:
        terminal_width = shutil.get_terminal_size().columns
    except Exception:  # pylint: disable=broad-except
        terminal_width = 120  # default value for Windows Terminal launch size columns
    column_widths = _calculate_column_widths(df, terminal_width)
    print(tabulate(df, headers="keys", tablefmt="grid", maxcolwidths=column_widths, maxheadercolwidths=column_widths))


def is_format_exception():
    if os.environ.get("PROMPTFLOW_STRUCTURE_EXCEPTION_OUTPUT", "false").lower() == "true":
        return True
    return False


def cli_exception_and_telemetry_handler(func, activity_name, custom_dimensions=None):
    """Catch known cli exceptions."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            telemetry_logger = get_telemetry_logger()
            with log_activity(
                telemetry_logger,
                activity_name,
                activity_type=ActivityType.PUBLICAPI,
                custom_dimensions=custom_dimensions,
            ):
                return func(*args, **kwargs)
        except Exception as e:
            if is_format_exception():
                # When the flag format_exception is set in command,
                # it will write a json with exception info and command to stderr.
                error_msg = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
                error_msg["command"] = " ".join(sys.argv)
                sys.stderr.write(json.dumps(error_msg))
            if isinstance(e, PromptflowException):
                print_red_error(f"{activity_name} failed with {e.__class__.__name__}: {str(e)}")
                sys.exit(1)
            else:
                raise e

    return wrapper


def get_secret_input(prompt, mask="*"):
    """Get secret input with mask printed on screen in CLI.

    Provide better handling for control characters:
    - Handle Ctrl-C as KeyboardInterrupt
    - Ignore control characters and print warning message.
    """
    if not isinstance(prompt, str):
        e = TypeError(f"prompt must be a str, not ${type(prompt).__name__}")
        raise UserErrorException(message_format=str(e)) from e
    if not isinstance(mask, str):
        e = TypeError(f"mask argument must be a one-character str, not ${type(mask).__name__}")
        raise UserErrorException(message_format=str(e)) from e
    if len(mask) != 1:
        e = ValueError("mask argument must be a one-character str")
        raise UserErrorException(message_format=str(e)) from e

    if sys.platform == "win32":
        # For some reason, mypy reports that msvcrt doesn't have getch, ignore this warning:
        from msvcrt import getch  # type: ignore
    else:  # macOS and Linux
        import termios
        import tty

        def getch():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch

    secret_input = []
    sys.stdout.write(prompt)
    sys.stdout.flush()

    while True:
        key = ord(getch())
        if key == 13:  # Enter key pressed.
            sys.stdout.write("\n")
            return "".join(secret_input)
        elif key == 3:  # Ctrl-C pressed.
            raise KeyboardInterrupt()
        elif key in (8, 127):  # Backspace/Del key erases previous output.
            if len(secret_input) > 0:
                # Erases previous character.
                sys.stdout.write("\b \b")  # \b doesn't erase the character, it just moves the cursor back.
                sys.stdout.flush()
                secret_input = secret_input[:-1]
        elif 0 <= key <= 31:
            msg = "\nThe last user input got ignored as it is control character."
            print_yellow_warning(msg)
            sys.stdout.write(prompt + mask * len(secret_input))
            sys.stdout.flush()
        else:
            # display the mask character.
            char = chr(key)
            sys.stdout.write(mask)
            sys.stdout.flush()
            secret_input.append(char)


def _copy_to_flow(flow_path, source_file):
    target = flow_path / source_file.name
    action = "Overwriting" if target.exists() else "Creating"
    if source_file.is_file():
        print(f"{action} {source_file.name}...")
        shutil.copy2(source_file, target)
    else:
        print(f"{action} {source_file.name} folder...")
        shutil.copytree(source_file, target, dirs_exist_ok=True)


def _output_result_list_with_format(result_list: List[Dict], output_format: CLIListOutputFormat) -> None:
    import pandas as pd

    if output_format == CLIListOutputFormat.TABLE:
        df = pd.DataFrame(result_list)
        df.fillna("", inplace=True)
        pretty_print_dataframe_as_table(df)
    elif output_format == CLIListOutputFormat.JSON:
        print(json.dumps(result_list, indent=4))
    else:
        warning_message = (
            f"Unknown output format {output_format!r}, accepted values are 'json' and 'table';"
            "will print using 'json'."
        )
        logger.warning(warning_message)
        print(json.dumps(result_list, indent=4))


def _get_cli_activity_name(cli, args):
    activity_name = cli
    if getattr(args, "action", None):
        activity_name += f".{args.action}"
    if getattr(args, "sub_action", None):
        activity_name += f".{args.sub_action}"

    return activity_name


def _try_delete_existing_run_record(run_name: str):
    from promptflow._sdk._errors import RunNotFoundError
    from promptflow._sdk._orm import RunInfo as ORMRun

    try:
        ORMRun.delete(run_name)
    except RunNotFoundError:
        pass


def get_instance_results(path: Union[str, Path]) -> List[Dict]:
    """Parse flow artifact jsonl files in a directory and return a list of dictionaries.

    This function takes a path to a directory as input. It reads all jsonl files in the directory,
    parses the json data, and returns a list of dictionaries. Each dictionary contains the following keys:
    'line_number', 'status', and all keys in 'inputs' and 'output'.

    .. example::
        000000000_000000000.jsonl
        000000001_000000001.jsonl
        000000002_000000002.jsonl

        Get a list of dict like this:
            {"line_number": 0, "status": "Completed", "inputs.name": "hod", "inputs.line_number": 2, "result": "res"}
            ...
            ...

    Note that inputs keys are prefixed with 'inputs.', but outputs keys are not.
    Don't ask me why, because runtime did it this way :p

    Args:
        path (Union[str, Path]): The path to the directory containing the jsonl files.

    Returns:
        List[Dict]: A list of dictionaries containing the parsed data.
    """
    path = Path(path)
    result = []
    for file in path.glob("*.jsonl"):
        with open(file, "r", encoding=DEFAULT_ENCODING) as f:
            for line in f:
                data = json.loads(line)
                run_info = data.get("run_info", {})
                inputs = run_info.get("inputs", None) or {}
                output = run_info.get("output", None) or {}  # output can be None for some cases
                record = {
                    "line_number": data.get("line_number"),
                    "status": run_info.get("status"),
                }
                record.update({f"inputs.{k}": v for k, v in inputs.items()})
                record.update(output)
                result.append(record)
    return result


def merge_jsonl_files(source_folder: Union[str, Path], output_folder: Union[str, Path], group_size: int = 25) -> None:
    """
    Merge .jsonl files from a source folder into groups and write the merged files to an output folder.

    This function groups .jsonl files from the source folder into groups of a specified size (25 by default).
    Each group of .jsonl files is merged into a single .jsonl file, where each line of the output file is a JSON object
    from a line in one of the input files. The output files are named after the first and last files in each group,
    and are written to the output folder.

    The source folder is not modified by this function. If the output folder does not exist, it is created.

    .. example::
        000000000_000000000.jsonl
        000000001_000000001.jsonl
        000000002_000000002.jsonl

        merged to: 000000000_0000000024.jsonl

    Args:
        source_folder (str): The path to the source folder containing the .jsonl files to merge.
        output_folder (str): The path to the output folder where the merged .jsonl files will be written.
        group_size (int, optional): The size of the groups of .jsonl files to merge. Defaults to 25.

    Returns:
        None
    """
    source_folder_path = Path(source_folder)
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    jsonl_files = sorted(source_folder_path.glob("*.jsonl"))

    for i in range(0, len(jsonl_files), group_size):
        group = jsonl_files[i : i + group_size]
        file_name_part_0 = str(i).zfill(9)
        file_name_part_1 = str(i + group_size - 1).zfill(9)
        output_file_name = f"{file_name_part_0}_{file_name_part_1}.jsonl"
        output_file_path = output_folder_path / output_file_name

        with output_file_path.open("w", encoding=DEFAULT_ENCODING) as output_file:
            for jsonl_file in group:
                with jsonl_file.open(encoding=DEFAULT_ENCODING) as input_file:
                    json_line = json.load(input_file)
                    json.dump(json_line, output_file, ensure_ascii=False)
                    output_file.write("\n")
