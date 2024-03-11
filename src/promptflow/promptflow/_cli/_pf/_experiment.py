# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json
from pathlib import Path
import datetime
import sys

from promptflow._cli._params import (
    AppendToDictAction,
    add_param_all_results,
    add_param_archived_only,
    add_param_include_archived,
    add_param_max_results,
    base_params,
)
from promptflow._cli._utils import activate_action, list_of_dict_to_dict
from promptflow._sdk._pf_client import PFClient
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow.exceptions import UserErrorException

logger = get_cli_sdk_logger()
_client = None


def _get_pf_client():
    global _client
    if _client is None:
        _client = PFClient()
    return _client


def add_param_template(parser):
    parser.add_argument("--template", type=str, required=True, help="The experiment template path.")


def add_param_name(parser):
    parser.add_argument("--name", "-n", type=str, help="The experiment name.")


def add_param_input(parser):
    parser.add_argument(
        "--inputs",
        action=AppendToDictAction,
        help="Input datas for the experiment. Example: --inputs data1=data1_val data2=data2_val",
        nargs="+",
    )


def add_param_stream(parser):
    parser.add_argument(
        "-s",
        "--stream",
        action="store_true",
        default=False,
        help="Indicates whether to stream the experiment execution logs to the console.",
    )


def add_experiment_create(subparsers):
    epilog = """
    Examples:

    # Create an experiment from a template:
    pf experiment create --template flow.exp.yaml
    """
    add_params = [add_param_template, add_param_name] + base_params

    create_parser = activate_action(
        name="create",
        description=None,
        epilog=epilog,
        add_params=add_params,
        subparsers=subparsers,
        help_message="Create an experiment.",
        action_param_name="sub_action",
    )
    return create_parser


def add_experiment_list(subparsers):
    epilog = """
    Examples:

    # List all experiments:
    pf experiment list
    """
    activate_action(
        name="list",
        description="List all experiments.",
        epilog=epilog,
        add_params=[
            add_param_max_results,
            add_param_all_results,
            add_param_archived_only,
            add_param_include_archived,
        ]
        + base_params,
        subparsers=subparsers,
        help_message="List all experiments.",
        action_param_name="sub_action",
    )


def add_experiment_show(subparsers):
    epilog = """
    Examples:

    # Get and show an experiment:
    pf experiment show -n my_experiment
    """
    activate_action(
        name="show",
        description="Show an experiment for promptflow.",
        epilog=epilog,
        add_params=[add_param_name] + base_params,
        subparsers=subparsers,
        help_message="Show an experiment for promptflow.",
        action_param_name="sub_action",
    )


def add_experiment_start(subparsers):
    epilog = """
    Examples:

    # Start a named experiment:
    pf experiment start -n my_experiment --inputs data1=data1_val data2=data2_val
    # Run an experiment by yaml file:
    pf experiment start --template path/to/my_experiment.exp.yaml --inputs data1=data1_val data2=data2_val
    """
    activate_action(
        name="start",
        description="Start an experiment.",
        epilog=epilog,
        add_params=[add_param_name, add_param_template, add_param_input, add_param_stream] + base_params,
        subparsers=subparsers,
        help_message="Start an experiment.",
        action_param_name="sub_action",
    )


def add_experiment_stop(subparsers):
    epilog = """
    Examples:

    # Stop an named experiment:
    pf experiment stop -n my_experiment
    # Stop an experiment started by yaml file:
    pf experiment stop --template path/to/my_experiment.exp.yaml
    """
    activate_action(
        name="stop",
        description="Stop an experiment.",
        epilog=epilog,
        add_params=[add_param_name, add_param_template] + base_params,
        subparsers=subparsers,
        help_message="Stop an experiment.",
        action_param_name="sub_action",
    )


def add_experiment_parser(subparsers):
    experiment_parser = subparsers.add_parser(
        "experiment",
        description="[Experimental] A CLI tool to manage experiment for prompt flow.",
        help="[Experimental] pf experiment. This is an experimental feature, and may change at any time.",
    )
    subparsers = experiment_parser.add_subparsers()
    add_experiment_create(subparsers)
    add_experiment_list(subparsers)
    add_experiment_show(subparsers)
    add_experiment_start(subparsers)
    add_experiment_stop(subparsers)
    experiment_parser.set_defaults(action="experiment")


def dispatch_experiment_commands(args: argparse.Namespace):
    if args.sub_action == "create":
        create_experiment(args)
    elif args.sub_action == "list":
        list_experiment(args)
    elif args.sub_action == "show":
        show_experiment(args)
    elif args.sub_action == "start":
        start_experiment(args)
    elif args.sub_action == "show-status":
        pass
    elif args.sub_action == "update":
        pass
    elif args.sub_action == "delete":
        pass
    elif args.sub_action == "stop":
        stop_experiment(args)
    elif args.sub_action == "test":
        pass
    elif args.sub_action == "clone":
        pass


def create_experiment(args: argparse.Namespace):
    if not Path(args.template).is_absolute():
        raise UserErrorException("Please provide the absolute path to the experiment template.")
    if not Path(args.template).exists():
        raise UserErrorException(f"Experiment template path {args.template} does not exist.")
    experiment_name = args.name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    experiment_name = experiment_name or f"{Path(args.template).parent.name}_{timestamp}"
    logger.debug("Creating experiment %s", experiment_name)
    exp = _get_pf_client()._pfs_client.create_experiment(name=experiment_name, template=args.template)
    print(json.dumps(exp.to_dict(), indent=4))


def list_experiment(args: argparse.Namespace):
    results = _get_pf_client()._pfs_client.list_experiment(
        max_results=args.max_results, all_results=args.all_results, archived_only=args.archived_only, include_archived=args.include_archived)
    print(json.dumps([result.to_dict() for result in results], indent=4))


def show_experiment(args: argparse.Namespace):
    result = _get_pf_client()._pfs_client.show_experiment(args.name)
    print(json.dumps(result.to_dict(), indent=4))


def test_experiment(args: argparse.Namespace):
    result = _get_pf_client()._experiments._test(args.name)
    print(json.dumps(result._to_dict(), indent=4))


def start_experiment(args: argparse.Namespace):
    if args.name:
        logger.debug(f"Starting a named experiment {args.name}.")
        if args.inputs:
            inputs = None
            logger.warning("The inputs of named experiment cannot be modified.")
    elif args.template:
        logger.debug(f"Starting an anonymous experiment {args.template}.")
        inputs = list_of_dict_to_dict(args.inputs)
    else:
        raise UserErrorException("To start an experiment, one of [name, template] must be specified.")
    client = _get_pf_client()
    result = client._pfs_client.start_experiment(
        name=args.name, template=args.template, executable_path=sys.executable, inputs=inputs, stream=args.stream)
    print(json.dumps(result.to_dict(), indent=4))


def stop_experiment(args: argparse.Namespace):
    if any([args.name, args.template]):
        raise UserErrorException("To stop an experiment, one of [name, template] must be specified.")
    client = _get_pf_client()
    result = client._pfs_client.stop_experiment(name=args.name, template=args.template)
    print(json.dumps(result.to_dict(), indent=4))
