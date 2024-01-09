# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import functools
import json
from typing import Dict, List, Optional

from promptflow._cli._params import (
    add_param_all_results,
    add_param_archived_only,
    add_param_include_archived,
    add_param_max_results,
    add_param_output,
    add_param_output_format,
    add_param_overwrite,
    add_param_run_name,
    add_param_set,
    base_params,
)
from promptflow._cli._pf._run import _parse_metadata_args, add_run_create_common, create_run
from promptflow._cli._pf_azure._utils import _get_azure_pf_client
from promptflow._cli._utils import (
    _output_result_list_with_format,
    _set_workspace_argument_for_subparsers,
    activate_action,
    exception_handler,
    pretty_print_dataframe_as_table,
)
from promptflow._sdk._constants import MAX_SHOW_DETAILS_RESULTS, ListViewType
from promptflow._sdk._errors import InvalidRunStatusError
from promptflow._sdk._utils import print_red_error
from promptflow.azure._restclient.flow_service_caller import FlowRequestException


def add_parser_run(subparsers):
    """Add run parser to the pfazure subparsers."""
    run_parser = subparsers.add_parser(
        "run", description="A CLI tool to manage cloud runs for prompt flow.", help="Manage prompt flow runs."
    )
    subparsers = run_parser.add_subparsers()

    add_run_create_cloud(subparsers)
    add_parser_run_list(subparsers)
    add_parser_run_stream(subparsers)
    add_parser_run_show(subparsers)
    add_parser_run_show_details(subparsers)
    add_parser_run_show_metrics(subparsers)
    add_parser_run_cancel(subparsers)
    add_parser_run_visualize(subparsers)
    add_parser_run_archive(subparsers)
    add_parser_run_restore(subparsers)
    add_parser_run_update(subparsers)
    add_parser_run_download(subparsers)
    run_parser.set_defaults(action="run")


def add_run_create_cloud(subparsers):
    epilog = """
Example:

# Create a run with YAML file:
pfazure run create -f <yaml-filename>
# Create a run from flow directory and reference a run:
pfazure run create --flow <path-to-flow-directory> --data <path-to-data-file> --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run <run-name> --variant "${summarize_text_content.variant_0}" --stream
# Create a run from existing workspace flow
pfazure run create --flow azureml:<flow-name> --data <path-to-data-file> --column-mapping <key-value-pair>
# Create a run from existing registry flow
pfazure run create --flow azureml://registries/<registry-name>/models/<flow-name>/versions/<version> --data <path-to-data-file> --column-mapping <key-value-pair>
"""  # noqa: E501

    def add_param_data(parser):
        # cloud pf can also accept remote data
        parser.add_argument(
            "--data", type=str, help="Local path to the data file or remote data. e.g. azureml:name:version."
        )

    add_param_runtime = lambda parser: parser.add_argument("--runtime", type=str, help=argparse.SUPPRESS)  # noqa: E731
    add_param_reset = lambda parser: parser.add_argument(  # noqa: E731
        "--reset-runtime", action="store_true", help=argparse.SUPPRESS
    )
    add_run_create_common(
        subparsers,
        [add_param_data, add_param_runtime, add_param_reset, _set_workspace_argument_for_subparsers],
        epilog=epilog,
    )


def add_parser_run_list(subparsers):
    """Add run list parser to the pfazure subparsers."""
    epilog = """
Examples:

# List runs status:
pfazure run list
# List most recent 10 runs status:
pfazure run list --max-results 10
# List active and archived runs status:
pfazure run list --include-archived
# List archived runs status only:
pfazure run list --archived-only
# List all runs status as table:
pfazure run list --output table
"""

    add_params = [
        add_param_max_results,
        add_param_archived_only,
        add_param_include_archived,
        add_param_output_format,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="list",
        description="A CLI tool to List all runs.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="List runs in a workspace.",
        action_param_name="sub_action",
    )


def add_parser_run_stream(subparsers):
    """Add run stream parser to the pfazure subparsers."""
    epilog = """
Example:

# Stream run logs:
pfazure run stream --name <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="stream",
        description="A CLI tool to stream run logs to the console.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Stream run logs to the console.",
        action_param_name="sub_action",
    )


def add_parser_run_show(subparsers):
    """Add run show parser to the pfazure subparsers."""
    epilog = """
Example:

# Show the status of a run:
pfazure run show --name <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="show",
        description="A CLI tool to show a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show a run.",
        action_param_name="sub_action",
    )


def add_parser_run_show_details(subparsers):
    """Add run show details parser to the pfazure subparsers."""
    epilog = """
Example:

# View input(s) and output(s) of a run:
pfazure run show-details --name <name>
"""

    add_param_max_results = lambda parser: parser.add_argument(  # noqa: E731
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_SHOW_DETAILS_RESULTS,
        help=f"Number of lines to show. Default is {MAX_SHOW_DETAILS_RESULTS}.",
    )

    add_params = [
        add_param_max_results,
        add_param_run_name,
        add_param_all_results,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="show-details",
        description="A CLI tool to show a run details.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show a run details.",
        action_param_name="sub_action",
    )


def add_parser_run_show_metrics(subparsers):
    """Add run show metrics parser to the pfazure subparsers."""
    epilog = """
Example:

# View metrics of a run:
pfazure run show-metrics --name <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="show-metrics",
        description="A CLI tool to show run metrics.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show run metrics.",
        action_param_name="sub_action",
    )


def add_parser_run_cancel(subparsers):
    """Add run cancel parser to the pfazure subparsers."""
    epilog = """
Example:

# Cancel a run:
pfazure run cancel --name <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="cancel",
        description="A CLI tool to cancel a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Cancel a run.",
        action_param_name="sub_action",
    )


def add_parser_run_visualize(subparsers):
    """Add run visualize parser to the pfazure subparsers."""
    epilog = """
Examples:

# Visualize a run:
pfazure run visualize -n <name>
# Visualize runs:
pfazure run visualize --names "<name1,name2>"
pfazure run visualize --names "<name1>, <name2>"
"""
    add_param_name = lambda parser: parser.add_argument(  # noqa: E731
        "-n", "--names", type=str, required=True, help="Name of the runs, comma separated."
    )
    add_param_html_path = lambda parser: parser.add_argument(  # noqa: E731
        "--html-path", type=str, default=None, help=argparse.SUPPRESS
    )

    add_params = [
        add_param_name,
        add_param_html_path,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="visualize",
        description="A CLI tool to visualize a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Visualize a run.",
        action_param_name="sub_action",
    )


def add_parser_run_archive(subparsers):
    """Add run archive parser to the pfazure subparsers."""
    epilog = """
Examples:

# Archive a run:
pfazure run archive -n <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="archive",
        description="A CLI tool to archive a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Archive a run.",
        action_param_name="sub_action",
    )


def add_parser_run_restore(subparsers):
    """Add run restore parser to the pfazure subparsers."""
    epilog = """
Examples:

# Restore an archived run:
pfazure run restore -n <name>
"""
    add_params = [
        add_param_run_name,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="restore",
        description="A CLI tool to restore a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Restore a run.",
        action_param_name="sub_action",
    )


def add_parser_run_update(subparsers):
    """Add run update parser to the pfazure subparsers."""
    epilog = """
Example:

# Update a run metadata:
pfazure run update --name <name> --set display_name="<display-name>" description="<description>" tags.key="<value>"
"""
    add_params = [
        add_param_run_name,
        add_param_set,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="update",
        description="A CLI tool to update a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Update a run.",
        action_param_name="sub_action",
    )


def add_parser_run_download(subparsers):
    """Add run download parser to the pfazure subparsers."""
    epilog = """
Example:

# Download a run data to local:
pfazure run download --name <name> --output <output-folder-path>
"""
    add_params = [
        add_param_run_name,
        add_param_output,
        add_param_overwrite,
        _set_workspace_argument_for_subparsers,
    ] + base_params

    activate_action(
        name="download",
        description="A CLI tool to download a run.",
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Download a run.",
        action_param_name="sub_action",
    )


def dispatch_run_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
        create_run(
            create_func=functools.partial(
                pf.runs.create_or_update, runtime=args.runtime, reset_runtime=args.reset_runtime
            ),
            args=args,
        )
    elif args.sub_action == "list":
        list_runs(
            args.subscription,
            args.resource_group,
            args.workspace_name,
            args.max_results,
            args.archived_only,
            args.include_archived,
            args.output,
        )
    elif args.sub_action == "show":
        show_run(args.subscription, args.resource_group, args.workspace_name, args.name)
    elif args.sub_action == "show-details":
        show_run_details(
            args.subscription,
            args.resource_group,
            args.workspace_name,
            args.name,
            args.max_results,
            args.all_results,
            args.debug,
        )
    elif args.sub_action == "show-metrics":
        show_metrics(args.subscription, args.resource_group, args.workspace_name, args.name)
    elif args.sub_action == "stream":
        stream_run(args.subscription, args.resource_group, args.workspace_name, args.name, args.debug)
    elif args.sub_action == "visualize":
        visualize(
            args.subscription,
            args.resource_group,
            args.workspace_name,
            args.names,
            args.html_path,
            args.debug,
        )
    elif args.sub_action == "archive":
        archive_run(args.subscription, args.resource_group, args.workspace_name, args.name)
    elif args.sub_action == "restore":
        restore_run(args.subscription, args.resource_group, args.workspace_name, args.name)
    elif args.sub_action == "update":
        update_run(args.subscription, args.resource_group, args.workspace_name, args.name, params=args.params_override)
    elif args.sub_action == "download":
        download_run(args)
    elif args.sub_action == "cancel":
        cancel_run(args)


@exception_handler("List runs")
def list_runs(
    subscription_id,
    resource_group,
    workspace_name,
    max_results,
    archived_only,
    include_archived,
    output,
):
    """List all runs from cloud."""
    if max_results < 1:
        raise ValueError(f"'max_results' must be a positive integer, got {max_results!r}")

    # Default list_view_type is ACTIVE_ONLY
    if archived_only and include_archived:
        raise ValueError("Cannot specify both 'archived_only' and 'include_archived'")
    list_view_type = ListViewType.ACTIVE_ONLY
    if archived_only:
        list_view_type = ListViewType.ARCHIVED_ONLY
    if include_archived:
        list_view_type = ListViewType.ALL

    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    runs = pf.runs.list(max_results=max_results, list_view_type=list_view_type)
    # hide additional info, debug info and properties in run list for better user experience
    run_list = [
        run._to_dict(exclude_additional_info=True, exclude_debug_info=True, exclude_properties=True) for run in runs
    ]
    _output_result_list_with_format(result_list=run_list, output_format=output)
    return runs


@exception_handler("Show run")
def show_run(subscription_id, resource_group, workspace_name, run_name):
    """Show a run from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.get(run=run_name)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Show run details")
def show_run_details(subscription_id, resource_group, workspace_name, run_name, max_results, all_results, debug=False):
    """Show a run details from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    details = pf.runs.get_details(run=run_name, max_results=max_results, all_results=all_results)
    details.fillna(value="(Failed)", inplace=True)  # replace nan with explicit prompt
    pretty_print_dataframe_as_table(details)


@exception_handler("Show run metrics")
def show_metrics(subscription_id, resource_group, workspace_name, run_name):
    """Show run metrics from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    metrics = pf.runs.get_metrics(run=run_name)
    print(json.dumps(metrics, indent=4))


@exception_handler("Stream run")
def stream_run(subscription_id, resource_group, workspace_name, run_name, debug=False):
    """Stream run logs from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    run = pf.runs.stream(run_name)
    print("\n")
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Visualize run")
def visualize(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    names: str,
    html_path: Optional[str] = None,
    debug: bool = False,
):
    run_names = [name.strip() for name in names.split(",")]
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    try:
        pf.runs.visualize(run_names, html_path=html_path)
    except FlowRequestException as e:
        error_message = f"Visualize failed, request service error: {str(e)}"
        print_red_error(error_message)
    except InvalidRunStatusError as e:
        error_message = f"Visualize failed: {str(e)}"
        print_red_error(error_message)


@exception_handler("Archive run")
def archive_run(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    run_name: str,
):
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.archive(run=run_name)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Restore run")
def restore_run(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    run_name: str,
):
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.restore(run=run_name)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Update run")
def update_run(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    run_name: str,
    params: List[Dict[str, str]],
):
    # params_override can have multiple items when user specifies with
    # `--set key1=value1 key2=value`
    # so we need to merge them first.
    display_name, description, tags = _parse_metadata_args(params)
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.update(run=run_name, display_name=display_name, description=description, tags=tags)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Download run")
def download_run(args: argparse.Namespace):
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    pf.runs.download(run=args.name, output=args.output, overwrite=args.overwrite)


@exception_handler("Cancel run")
def cancel_run(args: argparse.Namespace):
    pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
    pf.runs.cancel(run=args.name)
