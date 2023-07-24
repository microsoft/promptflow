# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
import uuid
from functools import wraps
from typing import Callable, Dict, List, Optional, Tuple

from tabulate import tabulate

from promptflow._cli._params import add_param_set, add_parser_export
from promptflow._cli.utils import get_migration_secret_from_args
from promptflow.sdk._constants import MAX_LIST_CLI_RESULTS, MAX_SHOW_DETAILS_RESULTS, Color, get_list_view_type
from promptflow.sdk._load_functions import load_run
from promptflow.sdk._pf_client import PFClient
from promptflow.sdk._run_functions import _create_run
from promptflow.sdk.entities import Run
from promptflow.sdk.exceptions import InvalidRunStatusError, RunExistsError, RunNotFoundError


def add_run_parser(subparsers):
    run_parser = subparsers.add_parser("run", description="A CLI tool to manage runs for prompt flow.", help="pf run")
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
    add_parser_export(subparsers, "run")
    run_parser.set_defaults(action="run")


def add_run_create(subparsers):
    create_parser = subparsers.add_parser(
        "create", help="Create a run.", epilog="pf run create --file <local-path-to-yaml> [--stream]"
    )
    # pf run create --file batch_run.yaml [--stream]
    create_parser.add_argument(
        "-f", "--file", dest="file", type=str, help="Local path to the YAML file containing the run definition."
    )
    create_parser.add_argument(
        "-s",
        "--stream",
        action="store_true",
        default=False,
        help="Indicates whether to stream the run's logs to the console.",
    )
    # pf run create --type batch --flow ./flow_dir --data xx.jsonl \
    #   --inputs_mapping "xx=yy,aa=bb" --node_variant "${node_name.variant1}" --name "run1"
    create_parser.add_argument("--flow", type=str, help="Local path to the flow directory.")
    create_parser.add_argument("--data", type=str, help="Local path to the data file.")
    create_parser.add_argument(
        "--column-mapping",
        type=str,
        help="Inputs column mapping, use ${data.xx} to refer to data file columns, "
        "use ${run.inputs.xx} and ${run.outputs.xx} to refer to run inputs/outputs columns",
    )
    create_parser.add_argument(
        "--variant", type=str, help="Node & variant name in format of ${node_name.variant_name}."
    )
    create_parser.add_argument("--run", type=str, help="Referenced flow run name referenced by current run.")
    create_parser.add_argument("-n", "--name", type=str, help="Name of the run.")
    create_parser.set_defaults(sub_action="create")
    return create_parser


def add_run_cancel(subparsers):
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a run.", epilog="pf run cancel --name <name>")
    cancel_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    cancel_parser.set_defaults(sub_action="cancel")


def add_run_update(subparsers):
    update_parser = subparsers.add_parser(
        "update",
        help="Update a run metadata, including display name, description and tags.",
        epilog='pf run update --name <name> --set display_name="<display-name>" description="<description>" tag.key="<value>"',  # noqa: E501
    )
    update_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    add_param_set(update_parser)
    update_parser.set_defaults(sub_action="update")


def add_run_stream(subparsers):
    stream_parser = subparsers.add_parser(
        "stream", help="Stream run logs to the console.", epilog="pf run stream --name <name>"
    )
    stream_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    stream_parser.set_defaults(sub_action="stream")


def add_run_list(subparsers):
    list_parser = subparsers.add_parser(
        "list",
        help="List runs locally.",
        epilog="pf run list [--max-results 10] [--all-results] [--archived-only] [--include-archived]",
    )
    list_parser.add_argument(
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_LIST_CLI_RESULTS,
        help=f"Max number of results to return. Default is {MAX_LIST_CLI_RESULTS}.",
    )
    list_parser.add_argument(
        "--all-results",
        action="store_true",
        dest="all_results",
        default=False,
        help="Returns all results",
    )
    list_parser.add_argument(
        "--archived-only",
        action="store_true",
        dest="archived_only",
        default=False,
        help="List archived runs only.",
    )
    list_parser.add_argument(
        "--include-archived",
        action="store_true",
        dest="include_archived",
        default=False,
        help="List archived runs and active runs.",
    )
    list_parser.set_defaults(sub_action="list")


def add_run_show(subparsers):
    show_parser = subparsers.add_parser("show", help="Show details for a run.", epilog="pf run show --name <name>")
    show_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    show_parser.set_defaults(sub_action="show")


def add_run_show_details(subparsers):
    show_details_parser = subparsers.add_parser(
        "show-details", help="Preview a run's input(s) and output(s).", epilog="pf run show-details --name <name>"
    )
    show_details_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    show_details_parser.add_argument(
        "-r",
        "--max-results",
        dest="max_results",
        type=int,
        default=MAX_SHOW_DETAILS_RESULTS,
        help=f"Number of lines to show. Default is {MAX_SHOW_DETAILS_RESULTS}.",
    )
    show_details_parser.set_defaults(sub_action="show-details")


def add_run_show_metrics(subparsers):
    show_metrics_parser = subparsers.add_parser(
        "show-metrics", help="Print run metrics to the console.", epilog="pf run show-metrics --name <name>"
    )
    show_metrics_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    show_metrics_parser.set_defaults(sub_action="show-metrics")


def add_run_visualize(subparsers):
    visualize_parser = subparsers.add_parser(
        "visualize", help="Visualize a run.", epilog='pf run visualize "run1,run2"'
    )
    visualize_parser.add_argument("-n", "--names", type=str, required=True, help="Name of the runs, comma separated.")
    visualize_parser.add_argument("--html-path", type=str, default=None, help=argparse.SUPPRESS)
    visualize_parser.set_defaults(sub_action="visualize")


def add_run_archive(subparsers):
    archive_parser = subparsers.add_parser("archive", help="Archive a run.", epilog="pf run archive --name <name>")
    archive_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    archive_parser.set_defaults(sub_action="archive")


def add_run_restore(subparsers):
    restore_parser = subparsers.add_parser(
        "restore", help="Restore an archived run.", epilog="pf run restore --name <name>"
    )
    restore_parser.add_argument("-n", "--name", required=True, type=str, help="Name of the run.")
    restore_parser.set_defaults(sub_action="restore")


def dispatch_run_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_run(
            create_func=_create_run,
            file=args.file,
            flow=args.flow,
            data=args.data,
            column_mapping=args.column_mapping,
            variant=args.variant,
            name=args.name,
            run=args.run,
            stream=args.stream,
        )
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
        )
    elif args.sub_action == "show":
        show_run(name=args.name)
    elif args.sub_action == "show-details":
        show_run_details(name=args.name, max_results=args.max_results)
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
    else:
        raise ValueError(f"Unrecognized command: {args.sub_action}")


def _merge_params(params: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, str]]]:
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


def print_error(message: str) -> None:
    print(Color.RED + message + Color.END)


def exception_handler(command: str):
    """Catch known local run managment exceptions."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (InvalidRunStatusError, RunExistsError, RunNotFoundError) as e:
                print_error(f"{command} run failed: {str(e)}")

        return wrapper

    return decorator


@exception_handler("Update")
def update_run(name: str, params: List[Dict[str, str]]) -> None:
    # params_override can have multiple items when user specifies with
    # `--set key1=value1 --set key2=value`
    # so we need to merge them first.
    display_name, description, tags = _merge_params(params)
    pf_client = PFClient()
    pf_client.runs.update(
        name=name,
        display_name=display_name,
        description=description,
        tags=tags,
    )


@exception_handler("Stream")
def stream_run(name: str) -> None:
    pf_client = PFClient()
    pf_client.runs.stream(name=name)


def list_runs(
    max_results: int,
    all_results: bool,
    archived_only: bool,
    include_archived: bool,
) -> None:
    pf_client = PFClient()
    # aligned behaviour with v2 SDK, all_results will overwrite max_results
    if all_results:
        max_results = None
    runs = pf_client.runs.list(
        max_results=max_results,
        list_view_type=get_list_view_type(archived_only=archived_only, include_archived=include_archived),
    )
    json_list = [run._to_dict() for run in runs]
    print(json.dumps(json_list, indent=4))


@exception_handler("Show")
def show_run(name: str) -> None:
    pf_client = PFClient()
    run = pf_client.runs.get(name=name)
    print(json.dumps(run._to_dict(), indent=4))


@exception_handler("Show details")
def show_run_details(name: str, max_results: int) -> None:
    pf_client = PFClient()
    details = pf_client.runs.get_details(name=name)
    print(tabulate(details.head(max_results), headers="keys", tablefmt="psql"))


@exception_handler("Show metrics")
def show_run_metrics(name: str) -> None:
    pf_client = PFClient()
    metrics = pf_client.runs.get_metrics(name=name)
    print(json.dumps(metrics, indent=4))


@exception_handler("Visualize")
def visualize_run(names: str, html_path: Optional[str] = None) -> None:
    run_names = names.split(",")
    pf_client = PFClient()
    pf_client.runs.visualize(run_names, html_path=html_path)


@exception_handler("Archive")
def archive_run(name: str) -> None:
    pf_client = PFClient()
    pf_client.runs.archive(name=name)


@exception_handler("Restore")
def restore_run(name: str) -> None:
    pf_client = PFClient()
    pf_client.runs.restore(name=name)


def _parse_kv_pair(kv_pairs: str) -> Dict[str, str]:
    result = {}
    for kv_pairs in kv_pairs.split(","):
        kv_pair = kv_pairs.strip()
        if "=" not in kv_pair:
            raise ValueError(f"Invalid key-value pair: {kv_pair}")
        key, value = kv_pair.split("=", 1)
        result[key] = value
    return result


@exception_handler("Create")
def create_run(
    create_func: Callable,
    file=None,
    flow=None,
    data=None,
    column_mapping=None,
    variant=None,
    run=None,
    name=None,
    stream=None,
):
    if file:
        params_override = []
        for param_key, param in {
            "name": name,
            "flow": flow,
            "variant": variant,
            "data": data,
            "column_mapping": column_mapping,
            "run": run,
        }.items():
            if not param:
                continue
            params_override.append({param_key: param})

        run = load_run(source=file, params_override=params_override)
    elif flow is None:
        raise ValueError("--flow is required when not using --file.")
    else:
        if column_mapping:
            column_mapping = _parse_kv_pair(column_mapping)

        run_data = {
            "name": name or str(uuid.uuid4()),
            "flow": flow,
            "data": data,
            "column_mapping": column_mapping,
            "run": run,
            "variant": variant,
        }
        # remove empty fields
        run_data = {k: v for k, v in run_data.items() if v is not None}

        run = Run._load(data=run_data)
    run = create_func(run=run, stream=stream)
    print(json.dumps(run._to_dict(), indent=4))


def export_run(args):
    _ = get_migration_secret_from_args(args)
    raise NotImplementedError()
