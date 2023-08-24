# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import functools
import json
import logging
from typing import Optional

import pandas as pd

from promptflow._cli._params import add_param_debug, add_param_run_name, add_param_verbose, logging_params
from promptflow._cli._pf._run import add_run_create_common, create_run
from promptflow._cli._pf_azure._utils import _get_azure_pf_client
from promptflow._cli._utils import (
    _set_workspace_argument_for_subparsers,
    activate_action,
    exception_handler,
    pretty_print_dataframe_as_table,
)
from promptflow._sdk._constants import (
    LOGGER_NAME,
    MAX_LIST_CLI_RESULTS,
    MAX_SHOW_DETAILS_RESULTS,
    CLIListOutputFormat,
    ListViewType,
)
from promptflow._sdk._errors import InvalidRunStatusError
from promptflow._sdk._utils import print_red_error
from promptflow.azure._restclient.flow_service_caller import FlowRequestException


def add_parser_run(subparsers):
    """Add run parser to the pfazure subparsers."""
    run_parser = subparsers.add_parser(
        "run", description="A CLI tool to manage cloud runs for prompt flow.", help="Manage promptflow runs."
    )
    subparsers = run_parser.add_subparsers()

    add_run_create_cloud(subparsers)
    add_parser_run_list(subparsers)
    add_parser_run_stream(subparsers)
    add_parser_run_show(subparsers)
    add_parser_run_show_details(subparsers)
    add_parser_run_show_metrics(subparsers)
    # add_parser_run_cancel(subparsers)
    add_parser_run_visualize(subparsers)
    # add_parser_run_archive(subparsers)
    # add_parser_run_restore(subparsers)
    # add_parser_run_update(subparsers)
    run_parser.set_defaults(action="run")


def add_run_create_cloud(subparsers):
    def add_param_data(parser):
        # cloud pf can also accept remote data
        parser.add_argument(
            "--data", type=str, help="Local path to the data file or remote data. e.g. azureml:name:version."
        )

    add_param_runtime = lambda parser: parser.add_argument("--runtime", type=str, help=argparse.SUPPRESS)  # noqa: E731
    add_run_create_common(subparsers, [add_param_data, _set_workspace_argument_for_subparsers, add_param_runtime])


def add_parser_run_list(subparsers):
    """Add run list parser to the pfazure subparsers."""
    add_param_max_results = lambda parser: parser.add_argument(  # noqa: E731
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_LIST_CLI_RESULTS,
        help=f"Max number of results to return. Default is {MAX_LIST_CLI_RESULTS}, 100 at most.",
    )

    add_param_archived_only = lambda parser: parser.add_argument(  # noqa: E731
        "--archived-only",
        action="store_true",
        help="List archived runs only.",
    )

    add_param_include_archived = lambda parser: parser.add_argument(  # noqa: E731
        "--include-archived",
        action="store_true",
        help="List archived runs and active runs.",
    )

    add_param_output = lambda parser: parser.add_argument(  # noqa: E731
        "-o",
        "--output",
        dest="output",
        type=str,
        default=CLIListOutputFormat.JSON,
        help="Output format, accepted values are 'json' and 'table'. Default is 'json'.",
    )

    add_params = [
        add_param_max_results,
        add_param_archived_only,
        add_param_include_archived,
        add_param_output,
        _set_workspace_argument_for_subparsers,
    ] + logging_params

    activate_action(
        name="list",
        description="A CLI tool to List all runs.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="List runs in a workspace.",
        action_param_name="sub_action",
    )


def add_parser_run_stream(subparsers):
    """Add run stream parser to the pfazure subparsers."""
    run_stream_parser = subparsers.add_parser(
        "stream", description="A CLI tool to stream run logs to the console.", help="Stream run logs to the console."
    )
    _set_workspace_argument_for_subparsers(run_stream_parser)
    run_stream_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to stream.")
    add_param_debug(run_stream_parser)
    add_param_verbose(run_stream_parser)
    run_stream_parser.set_defaults(sub_action="stream")


def add_parser_run_show(subparsers):
    """Add run show parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="show",
        description="A CLI tool to show a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show a run.",
        action_param_name="sub_action",
    )


def add_parser_run_show_details(subparsers):
    """Add run show details parser to the pfazure subparsers."""

    add_param_max_results = lambda parser: parser.add_argument(  # noqa: E731
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_SHOW_DETAILS_RESULTS,
        help=f"Number of lines to show. Default is {MAX_SHOW_DETAILS_RESULTS}.",
    )

    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_max_results,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="show-details",
        description="A CLI tool to show a run details.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show a run details.",
        action_param_name="sub_action",
    )


def add_parser_run_show_metrics(subparsers):
    """Add run show metrics parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="show-metrics",
        description="A CLI tool to show run metrics.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Show run metrics.",
        action_param_name="sub_action",
    )


def add_parser_run_cancel(subparsers):
    """Add run cancel parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="cancel",
        description="A CLI tool to cancel a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Cancel a run.",
        action_param_name="sub_action",
    )


def add_parser_run_visualize(subparsers):
    """Add run visualize parser to the pfazure subparsers."""
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
    ] + logging_params

    activate_action(
        name="visualize",
        description="A CLI tool to visualize a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Visualize a run.",
        action_param_name="sub_action",
    )


def add_parser_run_archive(subparsers):
    """Add run archive parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="archive",
        description="A CLI tool to archive a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Archive a run.",
        action_param_name="sub_action",
    )


def add_parser_run_restore(subparsers):
    """Add run restore parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="restore",
        description="A CLI tool to restore a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Restore a run.",
        action_param_name="sub_action",
    )


def add_parser_run_update(subparsers):
    """Add run update parser to the pfazure subparsers."""
    add_params = [
        _set_workspace_argument_for_subparsers,
        add_param_run_name,
    ] + logging_params

    activate_action(
        name="update",
        description="A CLI tool to update a run.",
        epilog=None,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Update a run.",
        action_param_name="sub_action",
    )


def dispatch_run_commands(args: argparse.Namespace):
    # --verbose and --debug, enable debug logging
    if (hasattr(args, "verbose") and args.verbose) or (hasattr(args, "debug") and args.debug):
        for handler in logging.getLogger(LOGGER_NAME).handlers:
            handler.setLevel(logging.DEBUG)

    if args.sub_action == "create":
        pf = _get_azure_pf_client(args.subscription, args.resource_group, args.workspace_name, debug=args.debug)
        create_run(create_func=functools.partial(pf.runs.create_or_update, runtime=args.runtime), args=args)
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
            args.subscription, args.resource_group, args.workspace_name, args.name, args.max_results, args.debug
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
    run_list = [run._to_dict() for run in runs]
    if output == CLIListOutputFormat.TABLE:
        df = pd.DataFrame(run_list)
        df.fillna("", inplace=True)
        pretty_print_dataframe_as_table(df)
    elif output == CLIListOutputFormat.JSON:
        print(json.dumps(run_list, indent=4))
    else:
        logger = logging.getLogger(LOGGER_NAME)
        warning_message = (
            f"Unknown output format {output!r}, accepted values are 'json' and 'table';" "will print using 'json'."
        )
        logger.warning(warning_message)
        print(json.dumps(run_list, indent=4))
    return runs


@exception_handler("Show run")
def show_run(subscription_id, resource_group, workspace_name, flow_run_id):
    """Show a run from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.get(run=flow_run_id)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Show run details")
def show_run_details(subscription_id, resource_group, workspace_name, flow_run_id, max_results, debug=False):
    """Show a run details from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    details = pf.runs.get_details(run=flow_run_id)
    pretty_print_dataframe_as_table(details.head(max_results))


@exception_handler("Show run metrics")
def show_metrics(subscription_id, resource_group, workspace_name, flow_run_id):
    """Show run metrics from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    metrics = pf.runs.get_metrics(run=flow_run_id)
    print(json.dumps(metrics, indent=4))


@exception_handler("Stream run")
def stream_run(subscription_id, resource_group, workspace_name, flow_run_id, debug=False):
    """Stream run logs from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    run = pf.runs.stream(flow_run_id)
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
