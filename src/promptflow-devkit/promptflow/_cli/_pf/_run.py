# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional, Tuple

from promptflow._cli._params import (
    add_param_all_results,
    add_param_archived_only,
    add_param_columns_mapping,
    add_param_connections,
    add_param_environment_variables,
    add_param_include_archived,
    add_param_init,
    add_param_max_results,
    add_param_output_format,
    add_param_run_name,
    add_param_set,
    add_param_yes,
    add_parser_build,
    base_params,
)
from promptflow._cli._utils import (
    _output_result_list_with_format,
    activate_action,
    confirm,
    list_of_dict_to_dict,
    list_of_dict_to_nested_dict,
    pretty_print_dataframe_as_table,
)
from promptflow._sdk._constants import MAX_SHOW_DETAILS_RESULTS, get_list_view_type
from promptflow._sdk._load_functions import load_run
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._run_functions import _create_run, _resume_run
from promptflow._sdk._utilities.general_utils import generate_yaml_entry, safe_parse_object_list
from promptflow._sdk.entities import Run
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()


def add_run_parser(subparsers):
    run_parser = subparsers.add_parser(
        "run", description="A CLI tool to manage runs for prompt flow.", help="Manage runs."
    )
    subparsers = run_parser.add_subparsers()
    add_run_create(subparsers)
    # add_run_cancel(subparsers)
    add_run_update(subparsers)
    add_run_stream(subparsers)
    add_run_list(subparsers)
    add_run_show(subparsers)
    add_run_show_details(subparsers)
    add_run_show_metrics(subparsers)
    add_run_visualize(subparsers)
    add_run_archive(subparsers)
    add_run_restore(subparsers)
    add_run_delete(subparsers)
    add_parser_build(subparsers, "run")
    run_parser.set_defaults(action="run")


def add_run_create_common(subparsers, add_param_list, epilog: Optional[str] = None):
    # pf run create --file batch_run.yaml [--stream]
    add_param_file = lambda parser: parser.add_argument(  # noqa: E731
        "-f",
        "--file",
        dest="file",
        type=str,
        help="Local path to the YAML file containing the run definition. "
        "Reference https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json for the schema.",
    )
    add_param_stream = lambda parser: parser.add_argument(  # noqa: E731
        "-s",
        "--stream",
        action="store_true",
        default=False,
        help="Indicates whether to stream the run's logs to the console.",
    )
    add_param_flow = lambda parser: parser.add_argument(  # noqa: E731
        "--flow",
        type=str,
        help="Local path to the flow directory."
        "If --file is provided, this path should be relative path to the file.",
    )
    add_param_variant = lambda parser: parser.add_argument(  # noqa: E731
        "--variant", type=str, help="Node & variant name in format of ${node_name.variant_name}."
    )
    add_param_run = lambda parser: parser.add_argument(  # noqa: E731
        "--run",
        type=str,
        help="Referenced flow run name referenced by current run. "
        "For example, you can run an evaluation flow against an existing run.",
    )
    add_param_name = lambda parser: parser.add_argument("-n", "--name", type=str, help="Name of the run.")  # noqa: E731

    add_param_resume_from = lambda parser: parser.add_argument(  # noqa: E731
        "--resume-from", type=str, dest="resume_from", help="The existing run name to resume from."
    )  # noqa: E731

    add_params = [
        add_param_file,
        add_param_stream,
        add_param_flow,
        add_param_variant,
        add_param_run,
        add_param_name,
        add_param_columns_mapping,
        # add env var overwrite
        add_param_environment_variables,
        add_param_connections,
        add_param_set,
        add_param_resume_from,
        add_param_init,
    ] + base_params

    add_params.extend(add_param_list)
    create_parser = activate_action(
        name="create",
        description=None,
        epilog=epilog or "pf run create --file <local-path-to-yaml> [--stream]",
        add_params=add_params,
        subparsers=subparsers,
        help_message="Create a run.",
        action_param_name="sub_action",
    )
    return create_parser


def add_run_create(subparsers):
    epilog = """
Examples:

# Create a run with YAML file:
pf run create -f <yaml-filename>
# Create a run with YAML file and replace another data in the YAML file:
pf run create -f <yaml-filename> --data <path-to-new-data-file-relative-to-yaml-file>
# Create a run from flow directory and reference a run:
pf run create --flow <path-to-flow-directory> --data <path-to-data-file> --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run <run-name> --variant "${summarize_text_content.variant_0}" --stream  # noqa: E501
# Create a run from an existing run record folder:
pf run create --source <path-to-run-folder>
# Create a run resume from an existing run:
pf run create --resume-from <run-name>
# Create a run resume from an existing run, set the name, display_name, description and tags:
pf run create --resume-from <run-name> --name <new-run-name> --set display_name='A new run' description='my run description' tags.Type=Test
# Create a run with init kwargs:
pf run create -f <yaml-filename> --init key1=value1 key2=value2
"""

    # data for pf has different help doc than pfazure
    def add_param_data(parser):
        parser.add_argument(
            "--data",
            type=str,
            help="Local path to the data file." "If --file is provided, this path should be relative path to the file.",
        )

    def add_param_source(parser):
        parser.add_argument("--source", type=str, help="Local path to the existing run record folder.")

    add_run_create_common(subparsers, [add_param_data, add_param_source], epilog=epilog)


def add_run_cancel(subparsers):
    epilog = """
Example:

# Cancel a run:
pf run cancel --name <name>
"""
    add_params = [add_param_run_name] + base_params
    activate_action(
        name="cancel",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Cancel a run.",
        action_param_name="sub_action",
    )


def add_run_update(subparsers):
    epilog = """
Example:

# Update a run metadata:
pf run update --name <name> --set display_name="<display-name>" description="<description>" tags.key="<value>"
"""
    add_params = [
        add_param_run_name,
        add_param_set,
    ] + base_params
    activate_action(
        name="update",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Update a run metadata, including display name, description and tags.",
        action_param_name="sub_action",
    )


def add_run_stream(subparsers):
    epilog = """
Example:

# Stream run logs:
pf run stream --name <name>
"""
    add_params = [add_param_run_name] + base_params
    activate_action(
        name="stream",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Stream run logs to the console.",
        action_param_name="sub_action",
    )


def add_run_list(subparsers):
    epilog = """
Examples:

# List runs status:
pf run list
# List most recent 10 runs status:
pf run list --max-results 10
# List active and archived runs status:
pf run list --include-archived
# List archived runs status only:
pf run list --archived-only
# List all runs status:
pf run list --all-results
# List all runs status as table:
pf run list --output table
"""
    add_params = [
        add_param_max_results,
        add_param_all_results,
        add_param_archived_only,
        add_param_include_archived,
        add_param_output_format,
    ] + base_params

    activate_action(
        name="list",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="List runs.",
        action_param_name="sub_action",
    )


def add_run_show(subparsers):
    epilog = """
Example:

# Show the status of a run:
pf run show --name <name>
"""
    add_params = [add_param_run_name] + base_params

    activate_action(
        name="show",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show details for a run.",
        action_param_name="sub_action",
    )


def add_run_show_details(subparsers):
    epilog = """
Example:

# View input(s) and output(s) of a run:
pf run show-details --name <name>
"""
    add_param_max_results = lambda parser: parser.add_argument(  # noqa: E731
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_SHOW_DETAILS_RESULTS,
        help=f"Number of lines to show. Default is {MAX_SHOW_DETAILS_RESULTS}.",
    )

    add_params = [add_param_max_results, add_param_run_name, add_param_all_results] + base_params

    activate_action(
        name="show-details",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Preview a run's input(s) and output(s).",
        action_param_name="sub_action",
    )


def add_run_show_metrics(subparsers):
    epilog = """
Example:

# View metrics of a run:
pf run show-metrics --name <name>
"""
    add_params = [add_param_run_name] + base_params

    activate_action(
        name="show-metrics",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Print run metrics to the console.",
        action_param_name="sub_action",
    )


def add_run_visualize(subparsers):
    epilog = """
Examples:

# Visualize a run:
pf run visualize -n <name>
# Visualize runs:
pf run visualize --names "<name1,name2>"
pf run visualize --names "<name1>, <name2>"
"""

    add_param_name = lambda parser: parser.add_argument(  # noqa: E731
        "-n", "--names", type=str, required=True, help="Name of the runs, comma separated."
    )
    add_param_html_path = lambda parser: parser.add_argument(  # noqa: E731
        "--html-path", type=str, default=None, help=argparse.SUPPRESS
    )

    add_params = [add_param_name, add_param_html_path] + base_params

    activate_action(
        name="visualize",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Visualize a run.",
        action_param_name="sub_action",
    )


def add_run_delete(subparsers):
    epilog = """
Example:

# Caution: pf run delete is irreversible.
# This operation will delete the run permanently from your local disk.
# Both run entity and output data will be deleted.

# Delete a run:
pf run delete -n "<name>"
"""
    add_params = [add_param_run_name, add_param_yes] + base_params

    activate_action(
        name="delete",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Delete a run irreversible.",
        action_param_name="sub_action",
    )


def add_run_archive(subparsers):
    epilog = """
Example:

# Archive a run:
pf run archive --name <name>
"""
    add_params = [add_param_run_name] + base_params

    activate_action(
        name="archive",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Archive a run.",
        action_param_name="sub_action",
    )


def add_run_restore(subparsers):
    epilog = """
Example:

# Restore an archived run:
pf run restore --name <name>
"""
    add_params = [add_param_run_name] + base_params

    activate_action(
        name="restore",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Restore an archived run.",
        action_param_name="sub_action",
    )


def dispatch_run_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_run(create_func=_create_run, resume_func=_resume_run, args=args)
    elif args.sub_action == "update":
        update_run(name=args.name, params=args.params_override)
    elif args.sub_action == "stream":
        stream_run(name=args.name)
    elif args.sub_action == "list":
        list_runs(
            max_results=args.max_results,
            all_results=args.all_results,
            archived_only=args.archived_only,
            include_archived=args.include_archived,
            output=args.output,
        )
    elif args.sub_action == "show":
        show_run(name=args.name)
    elif args.sub_action == "show-details":
        show_run_details(name=args.name, max_results=args.max_results, all_results=args.all_results)
    elif args.sub_action == "show-metrics":
        show_run_metrics(name=args.name)
    elif args.sub_action == "visualize":
        visualize_run(names=args.names, html_path=args.html_path)
    elif args.sub_action == "archive":
        archive_run(name=args.name)
    elif args.sub_action == "restore":
        restore_run(name=args.name)
    elif args.sub_action == "export":
        export_run(args)
    elif args.sub_action == "delete":
        delete_run(args.name, args.yes)
    else:
        raise ValueError(f"Unrecognized command: {args.sub_action}")


def _parse_metadata_args(params: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, str]]]:
    display_name, description, tags = None, None, {}
    for param in params:
        for k, v in param.items():
            if k == "display_name":
                if display_name is not None:
                    raise ValueError("Duplicate argument: 'display_name'.")
                display_name = v
            elif k == "description":
                if description is not None:
                    raise ValueError("Duplicate argument: 'description'.")
                description = v
            elif k.startswith("tags."):
                tag_key = k.replace("tags.", "")
                if tag_key in tags:
                    raise ValueError(f"Duplicate argument: 'tags.{tag_key}'.")
                tags[tag_key] = v
    if len(tags) == 0:
        tags = None
    return display_name, description, tags


def update_run(name: str, params: List[Dict[str, str]]) -> None:
    # params_override can have multiple items when user specifies with
    # `--set key1=value1 key2=value`
    # so we need to merge them first.
    display_name, description, tags = _parse_metadata_args(params)
    pf_client = PFClient()
    run = pf_client.runs.update(
        name=name,
        display_name=display_name,
        description=description,
        tags=tags,
    )
    print(json.dumps(run._to_dict(), indent=4))


def stream_run(name: str) -> None:
    pf_client = PFClient()
    run = pf_client.runs.stream(name=name)
    print(json.dumps(run._to_dict(), indent=4))


def list_runs(
    max_results: int,
    all_results: bool,
    archived_only: bool,
    include_archived: bool,
    output,
):
    pf_client = PFClient()
    # aligned behaviour with v2 SDK, all_results will overwrite max_results
    if all_results:
        max_results = None
    runs = pf_client.runs.list(
        max_results=max_results,
        list_view_type=get_list_view_type(archived_only=archived_only, include_archived=include_archived),
    )
    # hide additional info and debug info in run list for better user experience
    parser = lambda run: run._to_dict(exclude_additional_info=True, exclude_debug_info=True)  # noqa: E731
    json_list = safe_parse_object_list(
        obj_list=runs,
        parser=parser,
        message_generator=lambda x: f"Error parsing run {x.name!r}, skipped.",
    )
    _output_result_list_with_format(result_list=json_list, output_format=output)
    return runs


def show_run(name: str) -> None:
    pf_client = PFClient()
    run = pf_client.runs.get(name=name)
    print(json.dumps(run._to_dict(), indent=4))


def show_run_details(name: str, max_results: int, all_results: bool) -> None:
    pf_client = PFClient()
    details = pf_client.runs.get_details(name=name, max_results=max_results, all_results=all_results)
    pretty_print_dataframe_as_table(details)


def show_run_metrics(name: str) -> None:
    pf_client = PFClient()
    metrics = pf_client.runs.get_metrics(name=name)
    print(json.dumps(metrics, indent=4))


def visualize_run(names: str, html_path: Optional[str] = None) -> None:
    run_names = [name.strip() for name in names.split(",")]
    pf_client = PFClient()
    pf_client.runs.visualize(run_names, html_path=html_path)


def archive_run(name: str) -> None:
    pf_client = PFClient()
    run = pf_client.runs.archive(name=name)
    print(json.dumps(run._to_dict(), indent=4))


def restore_run(name: str) -> None:
    pf_client = PFClient()
    run = pf_client.runs.restore(name=name)
    print(json.dumps(run._to_dict(), indent=4))


def _parse_kv_pair(kv_pairs: str) -> Dict[str, str]:
    result = {}
    for kv_pairs in kv_pairs.split(","):
        kv_pair = kv_pairs.strip()
        if "=" not in kv_pair:
            raise ValueError(f"Invalid key-value pair: {kv_pair}")
        key, value = kv_pair.split("=", 1)
        result[key] = value
    return result


@contextmanager
def _build_run_obj_context(file, flow, run_source, run_params, params_override):
    if file:
        for param_key, param in run_params.items():
            params_override.append({param_key: param})

        yield load_run(source=file, params_override=params_override)
    if flow:
        with generate_yaml_entry(entry=flow) as generated_flow_yaml:
            run_params["flow"] = generated_flow_yaml
            yield Run._load(data=run_params, params_override=params_override)
    if run_source:
        display_name, description, tags = _parse_metadata_args(params_override)
        processed_params = {
            "display_name": display_name,
            "description": description,
            "tags": tags,
        }
        yield Run._load_from_source(source=run_source, params_override=processed_params)
    if not file and not flow and not run_source:
        raise UserErrorException("To create a run, one of [file, flow, source] must be specified.")


def create_run(create_func: Callable, resume_func: Callable, args):
    file = args.file
    flow = args.flow
    has_source = hasattr(args, "source")
    run_source = getattr(args, "source", None)  # source is only available for pf args, not pfazure.
    data = args.data
    column_mapping = args.column_mapping
    variant = args.variant
    name = args.name
    run = args.run
    stream = args.stream
    environment_variables = args.environment_variables
    connections = args.connections
    resume_from = args.resume_from
    init = args.init
    params_override = args.params_override or []

    if environment_variables:
        environment_variables = list_of_dict_to_dict(environment_variables)
    if connections:
        connections = list_of_dict_to_nested_dict(connections)
    if column_mapping:
        column_mapping = list_of_dict_to_dict(column_mapping)
    if init:
        init = list_of_dict_to_dict(init)

    run_params = {
        "name": name,
        "flow": flow,
        "variant": variant,
        "data": data,
        "column_mapping": column_mapping,
        "run": run,
        "environment_variables": environment_variables,
        "connections": connections,
        "resume_from": resume_from,
        "init": init,
    }
    # remove empty fields
    run_params = {k: v for k, v in run_params.items() if v is not None}

    if sum([bool(resume_from), bool(file), bool(flow), bool(run_source)]) > 1:
        raise UserErrorException(
            "More than one is provided for exclusive options: [file, flow"
            f"{', source' if has_source else ''}, resume-from]"
        )

    if resume_from:
        if params_override:
            logger.debug(f"resume_from specified, append params override {params_override} to run params.")
            run_params.update(list_of_dict_to_nested_dict(params_override))
        logger.debug(f"Run params: {run_params}")
        run = resume_func(**run_params, stream=stream)
    else:
        with _build_run_obj_context(
            file=file, flow=flow, run_source=run_source, run_params=run_params, params_override=params_override
        ) as run_obj:
            run = create_func(run=run_obj, stream=stream)
    if stream:
        print("\n")  # change new line to show run info
    print(json.dumps(run._to_dict(), indent=4))


def delete_run(name: str, skip_confirm: bool = False) -> None:
    if confirm("Are you sure to delete run irreversibly?", skip_confirm):
        pf_client = PFClient()
        pf_client.runs.delete(name=name)
    else:
        print("The delete operation was canceled.")


def export_run(args):
    raise NotImplementedError()
