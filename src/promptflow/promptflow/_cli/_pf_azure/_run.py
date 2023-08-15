# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import functools
import json
import logging
from typing import Optional

from promptflow._cli._params import add_param_debug, add_param_verbose
from promptflow._cli._pf._run import add_run_create, create_run
from promptflow._cli._pf_azure._utils import _get_azure_pf_client
from promptflow._cli._utils import _set_workspace_argument_for_subparsers, pretty_print_dataframe_as_table
from promptflow._sdk._constants import LOGGER_NAME, MAX_LIST_CLI_RESULTS, MAX_SHOW_DETAILS_RESULTS, ListViewType
from promptflow._sdk._utils import print_red_error
from promptflow._sdk.exceptions import InvalidRunStatusError
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
    parser = add_run_create(subparsers)
    _set_workspace_argument_for_subparsers(parser)
    parser.add_argument("--runtime", type=str, help=argparse.SUPPRESS)
    add_param_debug(parser)


def add_parser_run_list(subparsers):
    """Add run list parser to the pfazure subparsers."""
    run_list_parser = subparsers.add_parser(
        "list", description="A CLI tool to List all runs.", help="List runs in a workspace."
    )
    _set_workspace_argument_for_subparsers(run_list_parser)
    run_list_parser.add_argument(
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_LIST_CLI_RESULTS,
        help=f"Max number of results to return. Default is {MAX_LIST_CLI_RESULTS}, 100 at most.",
    )
    run_list_parser.add_argument(
        "--archived-only",
        action="store_true",
        help="List archived runs only.",
    )
    run_list_parser.add_argument(
        "--include-archived",
        action="store_true",
        help="List archived runs and active runs.",
    )
    run_list_parser.set_defaults(sub_action="list")


def add_parser_run_stream(subparsers):
    """Add run stream parser to the pfazure subparsers."""
    run_stream_parser = subparsers.add_parser(
        "stream", description="A CLI tool to stream run logs to the console.", help="Stream run logs to the console."
    )
    _set_workspace_argument_for_subparsers(run_stream_parser)
    run_stream_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to stream.")
    add_param_debug(run_stream_parser)
    run_stream_parser.set_defaults(sub_action="stream")


def add_parser_run_show(subparsers):
    """Add run show parser to the pfazure subparsers."""
    run_show_parser = subparsers.add_parser("show", description="A CLI tool to show a run.", help="Show a run.")
    _set_workspace_argument_for_subparsers(run_show_parser)
    run_show_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to show.")
    run_show_parser.set_defaults(sub_action="show")


def add_parser_run_show_details(subparsers):
    """Add run show details parser to the pfazure subparsers."""
    run_show_details_parser = subparsers.add_parser(
        "show-details", description="A CLI tool to show a run details.", help="Show a run details."
    )
    _set_workspace_argument_for_subparsers(run_show_details_parser)
    run_show_details_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to show details.")
    run_show_details_parser.add_argument(
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_SHOW_DETAILS_RESULTS,
        help=f"Number of lines to show. Default is {MAX_SHOW_DETAILS_RESULTS}.",
    )
    add_param_debug(run_show_details_parser)
    run_show_details_parser.set_defaults(sub_action="show-details")


def add_parser_run_show_metrics(subparsers):
    """Add run show metrics parser to the pfazure subparsers."""
    run_show_metrics_parser = subparsers.add_parser(
        "show-metrics", description="A CLI tool to show run metrics.", help="Show run metrics."
    )
    _set_workspace_argument_for_subparsers(run_show_metrics_parser)
    run_show_metrics_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to show metrics.")
    run_show_metrics_parser.set_defaults(sub_action="show-metrics")


def add_parser_run_cancel(subparsers):
    """Add run cancel parser to the pfazure subparsers."""
    run_cancel_parser = subparsers.add_parser("cancel", description="A CLI tool to cancel a run.", help="Cancel a run.")
    _set_workspace_argument_for_subparsers(run_cancel_parser)
    run_cancel_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to cancel.")
    run_cancel_parser.set_defaults(sub_action="cancel")


def add_parser_run_visualize(subparsers):
    """Add run visualize parser to the pfazure subparsers."""
    run_visualize_parser = subparsers.add_parser(
        "visualize", description="A CLI tool to visualize a run.", help="Visualize a run."
    )
    _set_workspace_argument_for_subparsers(run_visualize_parser)
    run_visualize_parser.add_argument(
        "-n", "--names", type=str, required=True, help="Name of the runs, comma separated."
    )
    run_visualize_parser.add_argument("--html-path", type=str, default=None, help=argparse.SUPPRESS)
    add_param_debug(run_visualize_parser)
    add_param_verbose(run_visualize_parser)
    run_visualize_parser.set_defaults(sub_action="visualize")


def add_parser_run_archive(subparsers):
    """Add run archive parser to the pfazure subparsers."""
    run_archive_parser = subparsers.add_parser(
        "archive", description="A CLI tool to archive a run.", help="Archive a run."
    )
    _set_workspace_argument_for_subparsers(run_archive_parser)
    run_archive_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to archive.")
    run_archive_parser.set_defaults(sub_action="archive")


def add_parser_run_restore(subparsers):
    """Add run restore parser to the pfazure subparsers."""
    run_restore_parser = subparsers.add_parser(
        "restore", description="A CLI tool to restore a run.", help="Restore a run."
    )
    _set_workspace_argument_for_subparsers(run_restore_parser)
    run_restore_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to restore.")
    run_restore_parser.set_defaults(sub_action="restore")


def add_parser_run_update(subparsers):
    """Add run update parser to the pfazure subparsers."""
    run_update_parser = subparsers.add_parser(
        "update",
        description="A CLI tool to update a run.",
        help="Update a run.",
    )
    _set_workspace_argument_for_subparsers(run_update_parser)
    run_update_parser.add_argument("-n", "--name", type=str, required=True, help="The run name to update.")
    run_update_parser.set_defaults(sub_action="update")


def dispatch_run_commands(args: argparse.Namespace):
    if hasattr(args, "verbose") and args.verbose:
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


def list_runs(subscription_id, resource_group, workspace_name, max_results, archived_only, include_archived):
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
    print(json.dumps(run_list, indent=4))
    return runs


def show_run(subscription_id, resource_group, workspace_name, flow_run_id):
    """Show a run from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    run = pf.runs.get(run=flow_run_id)
    print(json.dumps(run._to_dict(), indent=4))


def show_run_details(subscription_id, resource_group, workspace_name, flow_run_id, max_results, debug=False):
    """Show a run details from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    details = pf.runs.get_details(run=flow_run_id)
    pretty_print_dataframe_as_table(details.head(max_results))


def show_metrics(subscription_id, resource_group, workspace_name, flow_run_id):
    """Show run metrics from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name)
    metrics = pf.runs.get_metrics(run=flow_run_id)
    print(json.dumps(metrics, indent=4))


def stream_run(subscription_id, resource_group, workspace_name, flow_run_id, debug=False):
    """Stream run logs from cloud."""
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    run = pf.runs.stream(flow_run_id)
    print("\n")
    print(json.dumps(run._to_dict(), indent=4))


def visualize(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    names: str,
    html_path: Optional[str] = None,
    debug: bool = False,
):
    run_names = names.split(",")
    pf = _get_azure_pf_client(subscription_id, resource_group, workspace_name, debug=debug)
    try:
        pf.runs.visualize(run_names, html_path=html_path)
    except FlowRequestException as e:
        error_message = f"Visualize failed, request service error: {str(e)}"
        print_red_error(error_message)
    except InvalidRunStatusError as e:
        error_message = f"Visualize failed: {str(e)}"
        print_red_error(error_message)
