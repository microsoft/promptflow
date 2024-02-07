# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import argparse
import json

from promptflow._cli._params import (
    add_param_all_results,
    add_param_archived_only,
    add_param_include_archived,
    add_param_max_results,
    base_params,
)
from promptflow._cli._utils import activate_action, exception_handler
from promptflow._sdk._constants import get_list_view_type
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._experiment import Experiment
from promptflow._utils.logger_utils import get_cli_sdk_logger

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

    # Start an experiment:
    pf experiment start -n my_experiment
    """
    activate_action(
        name="start",
        description="Start an experiment.",
        epilog=epilog,
        add_params=[add_param_name] + base_params,
        subparsers=subparsers,
        help_message="Start an experiment.",
        action_param_name="sub_action",
    )


def add_experiment_stop(subparsers):
    epilog = """
    Examples:

    # Stop an experiment:
    pf experiment stop -n my_experiment
    """
    activate_action(
        name="stop",
        description="Stop an experiment.",
        epilog=epilog,
        add_params=[add_param_name] + base_params,
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


@exception_handler("Create experiment")
def create_experiment(args: argparse.Namespace):
    from promptflow._sdk._load_functions import _load_experiment_template

    template_path = args.template
    logger.debug("Loading experiment template from %s", template_path)
    template = _load_experiment_template(source=template_path)
    logger.debug("Creating experiment from template %s", template.dir_name)
    experiment = Experiment.from_template(template, name=args.name)
    logger.debug("Creating experiment %s", experiment.name)
    exp = _get_pf_client()._experiments.create_or_update(experiment)
    print(json.dumps(exp._to_dict(), indent=4))


@exception_handler("List experiment")
def list_experiment(args: argparse.Namespace):
    list_view_type = get_list_view_type(archived_only=args.archived_only, include_archived=args.include_archived)
    results = _get_pf_client()._experiments.list(args.max_results, list_view_type=list_view_type)
    print(json.dumps([result._to_dict() for result in results], indent=4))


@exception_handler("Show experiment")
def show_experiment(args: argparse.Namespace):
    result = _get_pf_client()._experiments.get(args.name)
    print(json.dumps(result._to_dict(), indent=4))


@exception_handler("Start experiment")
def start_experiment(args: argparse.Namespace):
    result = _get_pf_client()._experiments.start(args.name)
    print(json.dumps(result._to_dict(), indent=4))


@exception_handler("Stop experiment")
def stop_experiment(args: argparse.Namespace):
    result = _get_pf_client()._experiments.stop(args.name)
    print(json.dumps(result._to_dict(), indent=4))
